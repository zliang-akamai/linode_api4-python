from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from urllib import parse

from linode_api4.errors import UnexpectedResponseError
from linode_api4.objects import (
    Base,
    DerivedBase,
    Instance,
    JSONObject,
    MappedObject,
    Property,
    Region,
    Type,
)


class KubeVersion(Base):
    """
    A KubeVersion is a version of Kubernetes that can be deployed on LKE.

    API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#kubernetes-version-view
    """

    api_endpoint = "/lke/versions/{id}"

    properties = {
        "id": Property(identifier=True),
    }


@dataclass
class LKEClusterControlPlaneACLAddressesOptions(JSONObject):
    """
    LKEClusterControlPlaneACLAddressesOptions are options used to configure
    IP ranges that are explicitly allowed to access an LKE cluster's control plane.
    """

    ipv4: Optional[List[str]] = None
    ipv6: Optional[List[str]] = None


@dataclass
class LKEClusterControlPlaneACLOptions(JSONObject):
    """
    LKEClusterControlPlaneACLOptions is used to set
    the ACL configuration of an LKE cluster's control plane.
    """

    enabled: Optional[bool] = None
    addresses: Optional[LKEClusterControlPlaneACLAddressesOptions] = None


@dataclass
class LKEClusterControlPlaneOptions(JSONObject):
    """
    LKEClusterControlPlaneOptions is used to configure
    the control plane of an LKE cluster during its creation.
    """

    high_availability: Optional[bool] = None
    acl: Optional[LKEClusterControlPlaneACLOptions] = None


@dataclass
class LKEClusterControlPlaneACLAddresses(JSONObject):
    """
    LKEClusterControlPlaneACLAddresses describes IP ranges that are explicitly allowed
    to access an LKE cluster's control plane.
    """

    ipv4: List[str] = None
    ipv6: List[str] = None


@dataclass
class LKEClusterControlPlaneACL(JSONObject):
    """
    LKEClusterControlPlaneACL describes the ACL configuration of an LKE cluster's
    control plane.
    """

    enabled: bool = False
    addresses: LKEClusterControlPlaneACLAddresses = None


class LKENodePoolNode:
    """
    AN LKE Node Pool Node is a helper class that is used to populate the "nodes"
    array of an LKE Node Pool, and set up an automatic relationship with the
    Linode Instance the Node represented.
    """

    def __init__(self, client, json):
        """
        Creates this NodePoolNode
        """
        #: The ID of this Node Pool Node
        self.id = json.get(
            "id"
        )  # why do these have an ID if they don't have an endpoint of their own?

        #: The ID of the Linode Instance this Node represents
        self.instance_id = json.get("instance_id")

        #: The Instance object backing this Node Pool Node
        self.instance = Instance(client, self.instance_id)

        #: The Status of this Node Pool Node
        self.status = json.get("status")


class LKENodePool(DerivedBase):
    """
    An LKE Node Pool describes a pool of Linode Instances that exist within an
    LKE Cluster.

    API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#node-pool-view
    """

    api_endpoint = "/lke/clusters/{cluster_id}/pools/{id}"
    derived_url_path = "pools"
    parent_id_name = "cluster_id"

    properties = {
        "id": Property(identifier=True),
        "cluster_id": Property(identifier=True),
        "type": Property(slug_relationship=Type),
        "disks": Property(),
        "disk_encryption": Property(),
        "count": Property(mutable=True),
        "nodes": Property(
            volatile=True
        ),  # this is formatted in _populate below
        "autoscaler": Property(mutable=True),
        "tags": Property(mutable=True, unordered=True),
    }

    def _populate(self, json):
        """
        Parse Nodes into more useful LKENodePoolNode objects
        """
        if json is not None and json != {}:
            new_nodes = [
                (
                    LKENodePoolNode(self._client, c)
                    if not isinstance(c, dict)
                    else c
                )
                for c in json["nodes"]
            ]
            json["nodes"] = new_nodes

        super()._populate(json)

    def recycle(self):
        """
        Deleted and recreates all Linodes in this Node Pool in a rolling fashion.
        Completing this operation may take several minutes.  This operation will
        cause all local data on Linode Instances in this pool to be lost.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#node-pool-recycle
        """
        self._client.post(
            "{}/recycle".format(LKENodePool.api_endpoint), model=self
        )
        self.invalidate()


class LKECluster(Base):
    """
    An LKE Cluster is a single k8s cluster deployed via Linode Kubernetes Engine.

    API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#kubernetes-cluster-view
    """

    api_endpoint = "/lke/clusters/{id}"

    properties = {
        "id": Property(identifier=True),
        "created": Property(is_datetime=True),
        "label": Property(mutable=True),
        "tags": Property(mutable=True, unordered=True),
        "updated": Property(is_datetime=True),
        "region": Property(slug_relationship=Region),
        "k8s_version": Property(slug_relationship=KubeVersion, mutable=True),
        "pools": Property(derived_class=LKENodePool),
        "control_plane": Property(mutable=True),
    }

    def invalidate(self):
        """
        Extends the default invalidation logic to drop cached properties.
        """
        if hasattr(self, "_api_endpoints"):
            del self._api_endpoints

        if hasattr(self, "_kubeconfig"):
            del self._kubeconfig

        if hasattr(self, "_control_plane_acl"):
            del self._control_plane_acl

        Base.invalidate(self)

    @property
    def api_endpoints(self):
        """
        A list of API Endpoints for this Cluster.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#kubernetes-api-endpoints-list

        :returns: A list of MappedObjects of the API Endpoints
        :rtype: List[MappedObject]
        """
        # This result appears to be a PaginatedList, but objects in the list don't
        # have IDs and can't be retrieved on their own, and it doesn't accept normal
        # pagination properties, so we're converting this to a list of strings.
        if not hasattr(self, "_api_endpoints"):
            results = self._client.get(
                "{}/api-endpoints".format(LKECluster.api_endpoint), model=self
            )

            self._api_endpoints = [MappedObject(**c) for c in results["data"]]

        return self._api_endpoints

    @property
    def kubeconfig(self):
        """
        The administrative Kubernetes Config used to access this cluster, encoded
        in base64.  Note that this config contains sensitive credentials to your
        cluster.

        To convert this config into a readable form, use python's `base64` module::

           import base64

           config = my_cluster.kubeconfig
           yaml_config = base64.b64decode(config)

           # write this config out to disk
           with open("/path/to/target/kubeconfig.yaml", "w") as f:
               f.write(yaml_config.decode())

        It may take a few minutes for a config to be ready when creating a new
        cluster; during that time this request may fail.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#kubeconfig-view

        :returns: The Kubeconfig file for this Cluster.
        :rtype: str
        """
        if not hasattr(self, "_kubeconfig"):
            result = self._client.get(
                "{}/kubeconfig".format(LKECluster.api_endpoint), model=self
            )

            self._kubeconfig = result["kubeconfig"]

        return self._kubeconfig

    @property
    def control_plane_acl(self) -> LKEClusterControlPlaneACL:
        """
        Gets the ACL configuration of this cluster's control plane.

        API Documentation: TODO

        :returns: The cluster's control plane ACL configuration.
        :rtype: LKEClusterControlPlaneACL
        """

        if not hasattr(self, "_control_plane_acl"):
            result = self._client.get(
                f"{LKECluster.api_endpoint}/control_plane_acl", model=self
            )

            self._control_plane_acl = result.get("acl")

        return LKEClusterControlPlaneACL.from_json(self._control_plane_acl)

    def node_pool_create(self, node_type, node_count, **kwargs):
        """
        Creates a new :any:`LKENodePool` for this cluster.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#node-pool-create

        :param node_type: The type of nodes to create in this pool.
        :type node_type: :any:`Type` or str
        :param node_count: The number of nodes to create in this pool.
        :type node_count: int
        :param kwargs: Any other arguments to pass to the API.  See the API docs
                       for possible values.

        :returns: The new Node Pool
        :rtype: LKENodePool
        """
        params = {
            "type": node_type,
            "count": node_count,
        }
        params.update(kwargs)

        result = self._client.post(
            "{}/pools".format(LKECluster.api_endpoint), model=self, data=params
        )
        self.invalidate()

        if not "id" in result:
            raise UnexpectedResponseError(
                "Unexpected response creating node pool!", json=result
            )

        return LKENodePool(self._client, result["id"], self.id, result)

    def cluster_dashboard_url_view(self):
        """
        Get a Kubernetes Dashboard access URL for this Cluster.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#kubernetes-cluster-dashboard-url-view

        :returns: The Kubernetes Dashboard access URL for this Cluster.
        :rtype: str
        """

        result = self._client.get(
            "{}/dashboard".format(LKECluster.api_endpoint), model=self
        )

        return result["url"]

    def kubeconfig_delete(self):
        """
        Delete and regenerate the Kubeconfig file for a Cluster.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#kubeconfig-delete
        """

        self._client.delete(
            "{}/kubeconfig".format(LKECluster.api_endpoint), model=self
        )

    def node_view(self, nodeId):
        """
        Get a specific Node by ID.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#node-view

        :param nodeId: ID of the Node to look up.
        :type nodeId: str

        :returns: The specified Node
        :rtype: LKENodePoolNode
        """

        node = self._client.get(
            "{}/nodes/{}".format(
                LKECluster.api_endpoint, parse.quote(str(nodeId))
            ),
            model=self,
        )

        return LKENodePoolNode(self._client, node)

    def node_delete(self, nodeId):
        """
        Delete a specific Node from a Node Pool.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#node-delete

        :param nodeId: ID of the Node to delete.
        :type nodeId: str
        """

        self._client.delete(
            "{}/nodes/{}".format(
                LKECluster.api_endpoint, parse.quote(str(nodeId))
            ),
            model=self,
        )

    def node_recycle(self, nodeId):
        """
        Recycle a specific Node from an LKE cluster.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#node-recycle

        :param nodeId: ID of the Node to recycle.
        :type nodeId: str
        """

        self._client.post(
            "{}/nodes/{}/recycle".format(
                LKECluster.api_endpoint, parse.quote(str(nodeId))
            ),
            model=self,
        )

    def cluster_nodes_recycle(self):
        """
        Recycles all nodes in all pools of a designated Kubernetes Cluster.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#cluster-nodes-recycle
        """

        self._client.post(
            "{}/recycle".format(LKECluster.api_endpoint), model=self
        )

    def cluster_regenerate(self):
        """
        Regenerate the Kubeconfig file and/or the service account token for a Cluster.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#kubernetes-cluster-regenerate
        """

        self._client.post(
            "{}/regenerate".format(LKECluster.api_endpoint), model=self
        )

    def service_token_delete(self):
        """
        Delete and regenerate the service account token for a Cluster.

        API Documentation: https://www.linode.com/docs/api/linode-kubernetes-engine-lke/#service-token-delete
        """

        self._client.delete(
            "{}/servicetoken".format(LKECluster.api_endpoint), model=self
        )

    def control_plane_acl_update(
        self, acl: Union[LKEClusterControlPlaneACLOptions, Dict[str, Any]]
    ) -> LKEClusterControlPlaneACL:
        """
        Updates the ACL configuration for this cluster's control plane.

        API Documentation: TODO

        :param acl: The ACL configuration to apply to this cluster.
        :type acl: LKEClusterControlPlaneACLOptions or Dict[str, Any]

        :returns: The updated control plane ACL configuration.
        :rtype: LKEClusterControlPlaneACL
        """
        if isinstance(acl, LKEClusterControlPlaneACLOptions):
            acl = acl.dict

        result = self._client.put(
            f"{LKECluster.api_endpoint}/control_plane_acl",
            model=self,
            data={"acl": acl},
        )

        acl = result.get("acl")

        self._control_plane_acl = result.get("acl")

        return LKEClusterControlPlaneACL.from_json(acl)

    def control_plane_acl_delete(self):
        """
        Deletes the ACL configuration for this cluster's control plane.
        This has the same effect as calling control_plane_acl_update with the `enabled` field
        set to False. Access controls are disabled and all rules are deleted.

        API Documentation: TODO
        """
        self._client.delete(
            f"{LKECluster.api_endpoint}/control_plane_acl", model=self
        )

        # Invalidate the cache so it is automatically refreshed on next access
        if hasattr(self, "_control_plane_acl"):
            del self._control_plane_acl
