#######################################################################################################################
# Bendy eye contruction rules:
#
#######################################################################################################################

import bpy
import re
from mathutils import Vector
from ...utils import copy_bone, flip_bone, put_bone
from ...utils import org, strip_org, strip_def, make_deformer_name, connected_children_names, make_mechanism_name
from ...utils import create_circle_widget, create_sphere_widget, create_widget, create_cube_widget
from ...utils import MetarigError
from ...utils import make_constraints_from_string, align_bone_y_axis
from ..widgets import create_eye_widget, create_eyes_widget
from .chainy_rig import ChainyRig
from .control_snapper import ControlSnapper


class Rig(ChainyRig):

    def __init__(self, obj, bone_name, params):

        super().__init__(obj, bone_name, params)
        self.control_snapper = ControlSnapper(self.obj, self.bones)

        self.lid_len = None
        self.lid_bones = self.get_eyelids()

        self.paired_eye = self.get_paired_eye()

    def get_eyelids(self):
        """
        Returns the main bones of the lids chain
        :return:
        """

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        lid_bones = []
        for child in edit_bones[self.bones['org'][0]].children:
            if not child.use_connect:
                lid_bones.append(child.name)

        # Rule check
        if len(lid_bones) != 2:
            raise MetarigError("Exactly 2 disconnected chains (lids) must be parented to main bone")

        eyelids_bones_dict = {'top': [], 'bottom': []}
        self.lid_len = len(connected_children_names(self.obj, lid_bones[0])) + 1

        # Check both have same length
        for lid in lid_bones:
            if len(connected_children_names(self.obj, lid)) != self.lid_len - 1:
                raise MetarigError("All lid chains must be the same length")

        if edit_bones[lid_bones[0]].tail.z < edit_bones[lid_bones[1]].tail.z:
            eyelids_bones_dict['top'].append(lid_bones[1])
            eyelids_bones_dict['bottom'].append(lid_bones[0])
        else:
            eyelids_bones_dict['top'].append(lid_bones[0])
            eyelids_bones_dict['bottom'].append(lid_bones[1])

        if not (len(eyelids_bones_dict['top']) == len(eyelids_bones_dict['bottom']) == 1):
            raise MetarigError("Badly drawn eyelids on %s" % self.bones['org'][0])

        return eyelids_bones_dict

    def get_paired_eye(self):
        """
        A paired eye must follow the name rule: <bone_name>.<suffix>.<extra> where suffix = L or R and
        the other elements must be the same
        :return:
        """

        new_bone_name_blocks = self.bones['org'][0].split('.')

        if new_bone_name_blocks[1] == 'R':
            new_bone_name_blocks[1] = 'L'
        elif new_bone_name_blocks[1] == 'L':
            new_bone_name_blocks[1] = 'R'

        paired_org = '.'.join(new_bone_name_blocks)

        if paired_org in self.obj.data.edit_bones:
            return paired_org
        else:
            return ''

    def create_mch(self):

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        self.bones['eye_mch'] = dict()
        self.bones['eye_mch']['eyelid_top'] = []
        self.bones['eye_mch']['eyelid_bottom'] = []
        self.bones['eye_mch']['eye_master'] = ''
        self.bones['eye_mch']['eye_master_tip'] = ''

        main_bone_name = strip_org(self.bones['org'][0])
        eye_mch_name = make_mechanism_name(main_bone_name)
        eye_mch_name = copy_bone(self.obj, self.bones['org'][0], eye_mch_name)
        self.bones['eye_mch']['eye_master'] = eye_mch_name

        eye_tip_mch_name = copy_bone(self.obj, self.orientation_bone, eye_mch_name)
        self.bones['eye_mch']['eye_master_tip'] = eye_tip_mch_name
        put_bone(self.obj, eye_tip_mch_name, edit_bones[eye_mch_name].tail)
        if self.orientation_bone == self.base_bone:
            align_bone_y_axis(self.obj, eye_tip_mch_name, Vector((0, 0, 1)))
        edit_bones[eye_tip_mch_name].length = 0.25 * edit_bones[eye_mch_name].length

        # top lid
        top_lid_chain = [self.lid_bones['top'][0]]
        top_lid_chain.extend(connected_children_names(self.obj, top_lid_chain[0]))
        for l_b in top_lid_chain:
            lid_m_name = copy_bone(self.obj, self.bones['org'][0], eye_mch_name)
            edit_bones[lid_m_name].tail = edit_bones[l_b].tail
            self.bones['eye_mch']['eyelid_top'].append(lid_m_name)

        # bottom lid
        bottom_lid_chain = [self.lid_bones['bottom'][0]]
        bottom_lid_chain.extend(connected_children_names(self.obj, bottom_lid_chain[0]))
        for l_b in bottom_lid_chain:
            lid_m_name = copy_bone(self.obj, self.bones['org'][0], eye_mch_name)
            edit_bones[lid_m_name].tail = edit_bones[l_b].tail
            self.bones['eye_mch']['eyelid_bottom'].append(lid_m_name)

    def create_def(self):
        super().create_def()

    def create_controls(self):

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        self.bones['eye_ctrl'] = dict()

        if self.orientation_bone == self.base_bone:
            axis = Vector((0, 0, 1))
        else:
            axis = edit_bones[self.orientation_bone].y_axis

        eye_ctrl_name = "master_" + strip_org(self.bones['org'][0])
        eye_ctrl = copy_bone(self.obj, self.bones['org'][0], eye_ctrl_name)
        self.bones['eye_ctrl']['master_eye'] = eye_ctrl

        eye_target_name = strip_org(self.bones['org'][0])
        eye_target = copy_bone(self.obj, self.orientation_bone, eye_target_name)
        self.bones['eye_ctrl']['eye_target'] = eye_target
        position = edit_bones[eye_ctrl].tail + 5 * edit_bones[eye_ctrl].length * edit_bones[eye_ctrl].y_axis
        put_bone(self.obj, eye_target, position)
        edit_bones[eye_target].length = 0.5 * edit_bones[self.base_bone].length
        align_bone_y_axis(self.obj, eye_target, axis)

        # make standard controls
        super().create_controls()
        top_chain = strip_org(self.lid_bones['top'][0])
        bottom_chain = strip_org(self.lid_bones['bottom'][0])

        if self.lid_len % 2 != 0:
            mid_index = int((self.lid_len + 1)/2)

            top_lid_master = copy_bone(self.obj, self.bones['ctrl'][top_chain][0])
            edit_bones[top_lid_master].length *= 1.5
            self.bones['eye_ctrl']['top_lid_master'] = top_lid_master
            mid_bone_1 = edit_bones[self.bones['ctrl'][top_chain][mid_index - 1]]
            mid_bone_2 = edit_bones[self.bones['ctrl'][top_chain][mid_index]]
            put_bone(self.obj, top_lid_master, (mid_bone_1.head + mid_bone_2.head)/2)
            align_bone_y_axis(self.obj, top_lid_master, axis)

            bottom_lid_master = copy_bone(self.obj, self.bones['ctrl'][bottom_chain][0])
            edit_bones[bottom_lid_master].length *= 1.5
            self.bones['eye_ctrl']['bottom_lid_master'] = bottom_lid_master
            mid_bone_1 = edit_bones[self.bones['ctrl'][bottom_chain][mid_index - 1]]
            mid_bone_2 = edit_bones[self.bones['ctrl'][bottom_chain][mid_index]]
            put_bone(self.obj, bottom_lid_master, (mid_bone_1.head + mid_bone_2.head)/2)
            align_bone_y_axis(self.obj, bottom_lid_master, axis)

        else:
            mid_index = int((self.lid_len) / 2)
            edit_bones[self.bones['ctrl'][top_chain][mid_index]].length *= 1.5
            edit_bones[self.bones['ctrl'][bottom_chain][mid_index]].length *= 1.5

        # create eyes master if eye has company
        if self.paired_eye and strip_org(self.paired_eye) in edit_bones:
            other_eye = strip_org(self.paired_eye)
            position = (edit_bones[eye_target].head + edit_bones[other_eye].head) / 2
            direction = edit_bones[eye_target].y_axis + edit_bones[other_eye].y_axis
            common_ctrl = strip_org(self.paired_eye.split('.')[0] + '_common')
            common_ctrl = copy_bone(self.obj, eye_target, common_ctrl)
            self.bones['eye_ctrl']['common'] = common_ctrl
            put_bone(self.obj, common_ctrl, position)
            align_bone_y_axis(self.obj, common_ctrl, direction)
            edit_bones[other_eye].parent = edit_bones[common_ctrl]
            edit_bones[eye_target].parent = edit_bones[common_ctrl]

        for ctrl in self.bones['ctrl'][top_chain]:
            align_bone_y_axis(self.obj, ctrl, axis)

        for ctrl in self.bones['ctrl'][bottom_chain]:
            align_bone_y_axis(self.obj, ctrl, axis)

    def parent_bones(self):
        """
        Parent eye bones
        :return:
        """

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        master_ctrl = self.bones['eye_ctrl']['master_eye']

        eye_mchs = []
        eye_mchs.extend(self.bones['eye_mch']['eyelid_top'])
        eye_mchs.extend(self.bones['eye_mch']['eyelid_bottom'])
        eye_mchs.append(self.bones['eye_mch']['eye_master'])
        eye_mchs.append(self.bones['eye_mch']['eye_master_tip'])

        for mch in eye_mchs:
            edit_bones[mch].parent = edit_bones[master_ctrl]

        eye_ctrls = []
        for chain in self.bones['ctrl']:
            eye_ctrls.extend(self.bones['ctrl'][chain])

        for ctrl in eye_ctrls:
            edit_bones[ctrl].parent = edit_bones[master_ctrl]

        super().parent_bones()

        # adjust parenting
        top_lid_chain = strip_org(self.lid_bones['top'][0])

        for i, lid_def in enumerate(self.bones['def'][top_lid_chain]):
            if i == 0:
                edit_bones[lid_def].parent = edit_bones[self.bones['eye_mch']['eyelid_bottom'][-1]]
            else:
                edit_bones[lid_def].parent = edit_bones[self.bones['eye_mch']['eyelid_top'][i-1]]

        bottom_lid_chain = strip_org(self.lid_bones['bottom'][0])

        for i, lid_def in enumerate(self.bones['def'][bottom_lid_chain]):
            if i == 0:
                edit_bones[lid_def].parent = edit_bones[self.bones['eye_mch']['eyelid_top'][-1]]
            else:
                edit_bones[lid_def].parent = edit_bones[self.bones['eye_mch']['eyelid_bottom'][i-1]]

    def make_constraints(self):

        """
        Make constraints
        :return:
        """

        bpy.ops.object.mode_set(mode='OBJECT')
        pose_bones = self.obj.pose.bones

        tip = self.bones['eye_mch']['eye_master_tip']
        owner = pose_bones[tip]
        subtarget = self.bones['eye_mch']['eye_master']
        make_constraints_from_string(owner, self.obj, subtarget, 'CL1.0WW1.0')

        for i, e_m in enumerate(self.bones['eye_mch']['eyelid_top']):
            owner = pose_bones[e_m]
            subtarget = self.get_ctrl_by_index(strip_org(self.lid_bones['top'][0]), i+1)
            make_constraints_from_string(owner, self.obj, subtarget, "DT1.0Y0.0")

        for i, e_m in enumerate(self.bones['eye_mch']['eyelid_bottom']):
            owner = pose_bones[e_m]
            subtarget = self.get_ctrl_by_index(strip_org(self.lid_bones['bottom'][0]), i+1)
            make_constraints_from_string(owner, self.obj, subtarget, "DT1.0Y0.0")

        eye_mch_name = pose_bones[self.bones['eye_mch']['eye_master']]
        subtarget = self.bones['eye_ctrl']['eye_target']
        make_constraints_from_string(eye_mch_name, self.obj, subtarget, "DT1.0Y0.0")

        if self.lid_len % 2 == 0:
            i = int(self.lid_len/2)
            central_ctrl_top = self.get_ctrl_by_index(strip_org(self.lid_bones['top'][0]), i)
            owner = pose_bones[central_ctrl_top]
            subtarget = tip
            make_constraints_from_string(owner, self.obj, subtarget, "CL0.5LL0.0")
            central_ctrl_bottom = self.get_ctrl_by_index(strip_org(self.lid_bones['bottom'][0]), i)
            owner = pose_bones[central_ctrl_bottom]
            subtarget = tip
            make_constraints_from_string(owner, self.obj, subtarget, "CL0.5LL0.0")
            influence = 0.6
            j = 1
            while True:
                if i + j == self.lid_len:
                    break

                ctrl_top_1 = self.get_ctrl_by_index(strip_org(self.lid_bones['top'][0]), i+j)
                owner = pose_bones[ctrl_top_1]
                subtarget = central_ctrl_top
                make_constraints_from_string(owner, self.obj, subtarget, "CL%sLL0.0" % influence)
                ctrl_top_2 = self.get_ctrl_by_index(strip_org(self.lid_bones['top'][0]), i-j)
                owner = pose_bones[ctrl_top_2]
                subtarget = central_ctrl_top
                make_constraints_from_string(owner, self.obj, subtarget, "CL%sLL0.0" % influence)

                ctrl_bottom_1 = self.get_ctrl_by_index(strip_org(self.lid_bones['bottom'][0]), i+j)
                owner = pose_bones[ctrl_bottom_1]
                subtarget = central_ctrl_bottom
                make_constraints_from_string(owner, self.obj, subtarget, "CL%sLL0.0" % influence)
                ctrl_bottom_2 = self.get_ctrl_by_index(strip_org(self.lid_bones['bottom'][0]), i-j)
                owner = pose_bones[ctrl_bottom_2]
                subtarget = central_ctrl_bottom
                make_constraints_from_string(owner, self.obj, subtarget, "CL%sLL0.0" % influence)

                influence -= 0.1
                j += 1

        else:

            top_lid_master = self.bones['eye_ctrl']['top_lid_master']
            owner = pose_bones[top_lid_master]
            subtarget = tip
            make_constraints_from_string(owner, self.obj, subtarget, "CL0.5LL0.0")

            bottom_lid_master = self.bones['eye_ctrl']['bottom_lid_master']
            owner = pose_bones[bottom_lid_master]
            subtarget = tip
            make_constraints_from_string(owner, self.obj, subtarget, "CL0.5LL0.0")

            influence = 0.6
            i = int((self.lid_len + 1)/2)
            j = 0

            while True:
                if i + j == self.lid_len:
                    break

                ctrl_top_1 = self.get_ctrl_by_index(strip_org(self.lid_bones['top'][0]), i + j)
                owner = pose_bones[ctrl_top_1]
                subtarget = top_lid_master
                make_constraints_from_string(owner, self.obj, subtarget, "CL%sLL0.0" % influence)
                ctrl_top_2 = self.get_ctrl_by_index(strip_org(self.lid_bones['top'][0]), i - 1 - j)
                owner = pose_bones[ctrl_top_2]
                make_constraints_from_string(owner, self.obj, subtarget, "CL%sLL0.0" % influence)

                ctrl_bottom_1 = self.get_ctrl_by_index(strip_org(self.lid_bones['bottom'][0]), i + j)
                owner = pose_bones[ctrl_bottom_1]
                subtarget = bottom_lid_master
                make_constraints_from_string(owner, self.obj, subtarget, "CL%sLL0.0" % influence)
                ctrl_bottom_2 = self.get_ctrl_by_index(strip_org(self.lid_bones['bottom'][0]), i - 1 - j)
                owner = pose_bones[ctrl_bottom_2]
                make_constraints_from_string(owner, self.obj, subtarget, "CL%sLL0.0" % influence)

                influence -= 0.1
                j += 1

        # make the standard chainy rig constraints
        super().make_constraints()

        # adjust constraints
        top_lid_chain = strip_org(self.lid_bones['top'][0])

        for i, lid_def in enumerate(self.bones['def'][top_lid_chain]):
            for cns in pose_bones[lid_def].constraints:
                if cns.type != "DAMPED_TRACK" and cns.type != "STRETCH_TO":
                    pose_bones[lid_def].constraints.remove(cns)
                else:
                    cns.subtarget = self.bones['eye_mch']['eyelid_top'][i]
                    cns.head_tail = 1.0

        bottom_lid_chain = strip_org(self.lid_bones['bottom'][0])

        for i, lid_def in enumerate(self.bones['def'][bottom_lid_chain]):
            for cns in pose_bones[lid_def].constraints:
                if cns.type != "DAMPED_TRACK" and cns.type != "STRETCH_TO":
                    pose_bones[lid_def].constraints.remove(cns)
                else:
                    cns.subtarget = self.bones['eye_mch']['eyelid_bottom'][i]
                    cns.head_tail = 1.0

    def create_widgets(self):

        bpy.ops.object.mode_set(mode='OBJECT')

        # master_eye
        eye_ctrl = self.bones['eye_ctrl']['master_eye']
        create_circle_widget(self.obj, eye_ctrl)

        # eye target
        eye_target = self.bones['eye_ctrl']['eye_target']
        create_eye_widget(self.obj, eye_target)

        # top lid master
        if 'top_lid_master' in self.bones['eye_ctrl']:
            top_lid_master = self.bones['eye_ctrl']['top_lid_master']
            create_sphere_widget(self.obj, top_lid_master)

        # bottom lid master
        if 'bottom_lid_master' in self.bones['eye_ctrl']:
            bottom_lid_master = self.bones['eye_ctrl']['bottom_lid_master']
            create_sphere_widget(self.obj, bottom_lid_master)

        if 'common' in self.bones['eye_ctrl']:
            common_ctrl = self.bones['eye_ctrl']['common']
            create_eyes_widget(self.obj, common_ctrl)

        super().create_widgets()

    def generate(self):
        self.create_mch()
        self.create_def()
        self.create_controls()
        self.parent_bones()

        self.control_snapper.aggregate_ctrls(same_parent=False)

        self.make_constraints()
        self.create_widgets()

        return [""]


def create_sample(obj):
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('eye.L')
    bone.head[:] = 0.0360, -0.0686, 0.1107
    bone.tail[:] = 0.0360, -0.0848, 0.1107
    bone.roll = 0.0000
    bone.use_connect = False
    bones['eye.L'] = bone.name
    bone = arm.edit_bones.new('lid.T.L')
    bone.head[:] = 0.0515, -0.0692, 0.1104
    bone.tail[:] = 0.0474, -0.0785, 0.1136
    bone.roll = 0.1166
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['eye.L']]
    bones['lid.T.L'] = bone.name
    bone = arm.edit_bones.new('lid.B.L')
    bone.head[:] = 0.0237, -0.0826, 0.1058
    bone.tail[:] = 0.0319, -0.0831, 0.1050
    bone.roll = -0.1108
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['eye.L']]
    bones['lid.B.L'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.001')
    bone.head[:] = 0.0474, -0.0785, 0.1136
    bone.tail[:] = 0.0394, -0.0838, 0.1147
    bone.roll = 0.0791
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.L']]
    bones['lid.T.L.001'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.001')
    bone.head[:] = 0.0319, -0.0831, 0.1050
    bone.tail[:] = 0.0389, -0.0826, 0.1050
    bone.roll = -0.0207
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.L']]
    bones['lid.B.L.001'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.002')
    bone.head[:] = 0.0394, -0.0838, 0.1147
    bone.tail[:] = 0.0317, -0.0832, 0.1131
    bone.roll = -0.0356
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.L.001']]
    bones['lid.T.L.002'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.002')
    bone.head[:] = 0.0389, -0.0826, 0.1050
    bone.tail[:] = 0.0472, -0.0781, 0.1068
    bone.roll = 0.0229
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.L.001']]
    bones['lid.B.L.002'] = bone.name
    bone = arm.edit_bones.new('lid.T.L.003')
    bone.head[:] = 0.0317, -0.0832, 0.1131
    bone.tail[:] = 0.0237, -0.0826, 0.1058
    bone.roll = 0.0245
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.T.L.002']]
    bones['lid.T.L.003'] = bone.name
    bone = arm.edit_bones.new('lid.B.L.003')
    bone.head[:] = 0.0472, -0.0781, 0.1068
    bone.tail[:] = 0.0515, -0.0692, 0.1104
    bone.roll = -0.0147
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['lid.B.L.002']]
    bones['lid.B.L.003'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['eye.L']]
    pbone.rigify_type = 'experimental.bendy_eye'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.002']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.T.L.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lid.B.L.003']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.edit_bones:
        bone.select = False
        bone.select_head = False
        bone.select_tail = False
    for b in bones:
        bone = arm.edit_bones[bones[b]]
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        arm.edit_bones.active = bone