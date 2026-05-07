package k8sorch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	k8sdeployments "github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/contorch/k8s/deployments"
	k8sservices "github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/contorch/k8s/services"
)

func (orch *K8sOrchestrator) getInfProxyRuntime(nodeId string) (string, int32, error) {
	node, exists := orch.availableNodes[nodeId]
	if !exists {
		return "", 0, fmt.Errorf("node %s not found in available nodes", nodeId)
	}

	imageType := node.Labels.Common.ImageType
	if imageType == "" {
		return "", 0, fmt.Errorf("node %s has no image type label", nodeId)
	}

	image, err := getInfProxyImage(imageType)
	if err != nil {
		return "", 0, err
	}

	return image, node.Labels.InfProxy.NodePort, nil
}

func (orch *K8sOrchestrator) CreateInfProxy(nodeId string, configFiles map[string]string, parentServiceURL string) error {
	if err := orch.createConfigMapFromFiles(common.GetInfProxyConfigMapName(nodeId), configFiles); err != nil {
		return err
	}

	image, nodePort, err := orch.getInfProxyRuntime(nodeId)
	if err != nil {
		return err
	}

	localServiceURL := fmt.Sprintf("http://%s", common.GetInfSvcClusterAddress(nodeId))
	deployment := k8sdeployments.BuildInfProxyDeployment(
		nodeId,
		orch.namespace,
		image,
		localServiceURL,
		parentServiceURL,
	)
	deployment.Spec.Template.Spec.NodeName = nodeId
	if err := orch.createDeployment(deployment); err != nil {
		return err
	}

	service := k8sservices.BuildInfProxyService(nodeId, nodePort)
	if err := orch.createService(service); err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) RemoveInfProxy(nodeId string) error {
	if err := orch.deleteService(common.GetInfProxySvcName(nodeId)); err != nil {
		return err
	}

	if err := orch.deleteDeployment(common.GetInfProxyDepName(nodeId)); err != nil {
		return err
	}

	return orch.deleteConfigMap(common.GetInfProxyConfigMapName(nodeId))
}