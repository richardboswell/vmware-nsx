# Copyright 2017 VMware, Inc.
# All Rights Reserved
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_log import log as logging

from neutron_fwaas.db.firewall import firewall_db  # noqa
from neutron_fwaas.db.firewall import firewall_router_insertion_db \
    as fw_r_ins_db

from vmware_nsx.services.fwaas.common import fwaas_callbacks as com_callbacks

LOG = logging.getLogger(__name__)


class NsxvFwaasCallbacks(com_callbacks.NsxFwaasCallbacks):
    """NSX-V RPC callbacks for Firewall As A Service - V1."""

    def should_apply_firewall_to_router(self, context, router, router_id):
        """Return True if the FWaaS rules should be added to this router."""
        if not super(NsxvFwaasCallbacks, self).should_apply_firewall_to_router(
            context, router_id):
            return False

        # get all the relevant router info
        # ("router" does not have all the fields)
        ctx_elevated = context.elevated()
        router_data = self.core_plugin.get_router(ctx_elevated, router['id'])
        if not router_data:
            LOG.error("Couldn't read router %s data", router['id'])
            return False

        if router_data.get('distributed'):
            # in case of a distributed-router:
            # router['id'] is the id of the neutron router (=tlr)
            # and router_id is the plr/tlr (the one that is being updated)
            if router_id == router['id']:
                # Do not add firewall rules on the tlr router.
                return False

        # Check if the FWaaS driver supports this router
        if not self.fwaas_driver.should_apply_firewall_to_router(router_data):
            return False

        return True

    def get_fwaas_rules_for_router(self, context, router_id):
        """Return the list of (translated) FWaaS rules for this router."""
        ctx_elevated = context.elevated()
        fw_id = self._get_router_firewall_id(ctx_elevated, router_id)
        if fw_id:
            return self._get_fw_applicable_rules(ctx_elevated, fw_id)
        return []

    # TODO(asarfaty): add this api to fwaas firewall-router-insertion-db
    def _get_router_firewall_id(self, context, router_id):
        entry = context.session.query(
            fw_r_ins_db.FirewallRouterAssociation).filter_by(
            router_id=router_id).first()
        if entry:
            return entry.fw_id

    def _get_fw_applicable_rules(self, context, fw_id):
        fw_list = self.fwplugin_rpc.get_firewalls_for_tenant(context)
        for fw in fw_list:
            if fw['id'] == fw_id:
                return self.fwaas_driver.get_firewall_translated_rules(fw)
        return []
