import bpy
from ...utils import connected_children_names, strip_org, make_mechanism_name, copy_bone, make_deformer_name, put_bone
from ...utils import create_sphere_widget, strip_def
from ...utils import MetarigError

from .base_rig import BaseRig


class ChainyRig(BaseRig):

    CTRL_SCALE = 0.1
    MCH_SCALE = 0.3

    def __init__(self, obj, bone_name, params):

        super().__init__(obj, bone_name, params)

        self.chains = self.get_chains()

    def get_chains(self):
            """
            Returns all the ORG bones starting a chain in the rig and their subchains start bones
            :return:
            """

            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = self.obj.data.edit_bones

            chains = dict()

            for name in self.bones['org'][1:]:
                eb = edit_bones[name]
                if not eb.use_connect and eb.parent == edit_bones[self.base_bone]:
                    chains[name] = self.get_subchains(name)

            return chains

    def get_subchains(self, name):
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        subchains = []

        chain = [name]
        chain.extend(connected_children_names(self.obj, name))
        for bone in edit_bones[name].children:
            if self.obj.pose.bones[bone.name].rigify_type == "" and not bone.use_connect:
                if len(connected_children_names(self.obj, bone.name)) != len(chain) - 1:
                    raise MetarigError("Subchains of chain starting with %s are not the same length! assign a rig_type/"
                                       "unconnected children of main bone of chain" % name)
                else:
                    subchains.append(bone.name)

        return subchains

    def make_mch_chain(self, first_name):
        """
        Create all MCHs needed on a single chain
        :param first_name: name of the first bone in the chain
        :return:
        """

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        chain = [first_name]
        chain.extend(connected_children_names(self.obj, first_name))
        self.bones['mch'][strip_org(first_name)] = []

        for chain_bone in chain:
            mch = copy_bone(self.obj, chain_bone, assign_name=make_mechanism_name(strip_org(chain_bone)))
            edit_bones[mch].parent = None
            edit_bones[mch].length *= self.MCH_SCALE
            self.bones['mch'][strip_org(first_name)].append(mch)

    def create_mch(self):

        for name in self.chains:
            self.make_mch_chain(name)

            for subname in self.chains[name]:
                self.make_mch_chain(subname)

    def make_def_chain(self, first_name):
        """
        Creates all DEFs in chain
        :param first_name:
        :return:
        """

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        chain = [first_name]
        chain.extend(connected_children_names(self.obj, first_name))
        self.bones['def'][strip_org(first_name)] = []

        for chain_bone in chain:
            def_bone = copy_bone(self.obj, chain_bone, assign_name=make_deformer_name(strip_org(chain_bone)))
            edit_bones[def_bone].parent = None
            self.bones['def'][strip_org(first_name)].append(def_bone)

    def create_def(self):

        for name in self.chains:
            self.make_def_chain(name)

            for subname in self.chains[name]:
                self.make_def_chain(subname)

    def make_ctrl_chain(self, first_name):
        """
        Create all ctrls in chain
        :param first_name:
        :return:
        """

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        chain = [first_name]
        chain.extend(connected_children_names(self.obj, first_name))
        self.bones['ctrl'][strip_org(first_name)] = []

        for chain_bone in chain:
            ctrl = copy_bone(self.obj, self.bones['org'][0], assign_name=strip_org(chain_bone))
            put_bone(self.obj, ctrl, edit_bones[chain_bone].head)
            edit_bones[ctrl].length *= self.CTRL_SCALE
            self.bones['ctrl'][strip_org(first_name)].append(ctrl)

        last_name = chain[-1]
        last_ctrl = copy_bone(self.obj, self.bones['org'][0], assign_name=strip_org(last_name))
        put_bone(self.obj, last_ctrl, edit_bones[last_name].tail)
        edit_bones[last_ctrl].length *= self.CTRL_SCALE
        self.bones['ctrl'][strip_org(first_name)].append(last_ctrl)

    def create_controls(self):

        for name in self.chains:
            self.make_ctrl_chain(name)

            for subname in self.chains[name]:
                self.make_ctrl_chain(subname)

    def get_ctrl_by_index(self, chain, index):
        """
        Return ctrl in index position of chain
        :param chain:
        :param index:
        :return: bone name
        :rtype: str
        """

        ctrl_chain = self.bones['ctrl'][chain]
        if index >= len(ctrl_chain):
            return ""

        return ctrl_chain[index]

    def parent_bones(self):
        """
        Specify bone parenting
        :return:
        """

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        ### PARENT chain MCH-bones ###
        for subchain in self.bones['mch']:
            for i, name in enumerate(self.bones['mch'][subchain]):
                mch_bone = edit_bones[name]
                parent = self.get_ctrl_by_index(chain=subchain, index=i)
                if parent:
                    mch_bone.parent = edit_bones[parent]

        ### PARENT subchain sibling controls ###
        for chain in self.chains:
            for subchain in self.chains[chain]:
                for i, ctrl in enumerate(self.bones['ctrl'][strip_org(subchain)]):
                    ctrl_bone = edit_bones[ctrl]
                    parent = self.get_ctrl_by_index(chain=strip_org(chain), index=i)
                    if parent:
                        ctrl_bone.parent = edit_bones[parent]

    def make_constraints(self):
        """
        Make constraints for each bone subgroup
        :return:
        """

        bpy.ops.object.mode_set(mode='OBJECT')
        pose_bones = self.obj.pose.bones

        ### Constrain DEF-bones ###
        for subchain in self.bones['def']:
            for i, name in enumerate(self.bones['def'][subchain]):
                owner_pb = pose_bones[name]

                subtarget = make_mechanism_name(strip_def(name))
                const = owner_pb.constraints.new('COPY_LOCATION')
                const.target = self.obj
                const.subtarget = subtarget

                tail_subtarget = self.get_ctrl_by_index(chain=subchain, index=i+1)

                if tail_subtarget:
                    const = owner_pb.constraints.new('DAMPED_TRACK')
                    const.target = self.obj
                    const.subtarget = tail_subtarget

                    const = owner_pb.constraints.new('STRETCH_TO')
                    const.target = self.obj
                    const.subtarget = tail_subtarget

    def create_widgets(self):

        bpy.ops.object.mode_set(mode='OBJECT')
        for chain in self.bones['ctrl']:
            for ctrl in self.bones['ctrl'][chain]:
                create_sphere_widget(self.obj, ctrl)

    def generate(self):

        self.create_mch()
        self.create_def()
        self.create_controls()
        self.parent_bones()

        self.make_constraints()
        self.create_widgets()

        return [""]
