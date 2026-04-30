package k8sorch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	k8sdeployments "github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/contorch/k8s/deployments"
	k8sservices "github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/contorch/k8s/services"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
)

func getInfServicePVCName(nodeType, nodeId string) (string, error) {
	switch nodeType {
	case common.FL_TYPE_GLOBAL_AGGREGATOR:
		return common.GetGlAggPVCName(nodeId), nil
	case common.FL_TYPE_LOCAL_AGGREGATOR:
		return common.GetLocAggPVCName(nodeId), nil
	case common.FL_TYPE_CLIENT:
		return common.GetClientPVCName(nodeId), nil
	default:
		return "", fmt.Errorf("unsupported FL node type for inference service: %s", nodeType)
	}
}

func (orch *K8sOrchestrator) getInfServiceRuntime(nodeId string) (string, bool, error) {
	node, exists := orch.availableNodes[nodeId]
	if !exists {
		return "", false, fmt.Errorf("node %s not found in available nodes", nodeId)
	}

	imageType := node.Labels.Common.ImageType
	if imageType == "" {
		return "", false, fmt.Errorf("node %s has no image type label", nodeId)
	}

	image, err := getInfServiceImage(imageType)
	if err != nil {
		return "", false, err
	}

	
	useMPS := node.Labels.Common.UseMPS
	return image, useMPS, nil
}

func (orch *K8sOrchestrator) CreateInfService(nodeType string, nodeId string, configFiles map[string]string) error {
	pvcName, err := getInfServicePVCName(nodeType, nodeId)
	if err != nil {
		return err
	}

	err = orch.createConfigMapFromFiles(common.GetInfSvcConfigMapName(nodeId), configFiles)
	if err != nil {
		return err
	}

	image, useMPS, err := orch.getInfServiceRuntime(nodeId)
	if err != nil {
		return err
	}

	deployment := k8sdeployments.BuildInfServiceDeployment(nodeId, pvcName, orch.namespace, image, useMPS)
	deployment.Spec.Template.Spec.NodeName = nodeId
	err = orch.createDeployment(deployment)
	if err != nil {
		return err
	}

	service := k8sservices.BuildInfServiceService(nodeId)
	err = orch.createService(service)
	if err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) RemoveInfService(nodeId string) error {
	err := orch.deleteService(common.GetInfSvcSvcName(nodeId))
	if err != nil {
		return err
	}

	err = orch.deleteDeployment(common.GetInfSvcDepName(nodeId))
	if err != nil {
		return err
	}

	err = orch.deleteConfigMap(common.GetInfSvcConfigMapName(nodeId))
	if err != nil {
		return err
	}

	return nil
}

// Compatibility wrappers
func (orch *K8sOrchestrator) CreateGlobalAggregatorServing(aggregator *model.FlAggregator, configFiles map[string]string) error {
	return orch.CreateInfService(common.FL_TYPE_GLOBAL_AGGREGATOR, aggregator.Id, configFiles)
}

func (orch *K8sOrchestrator) RemoveGlobalAggregatorServing(aggregator *model.FlAggregator) error {
	return orch.RemoveInfService(aggregator.Id)
}

func (orch *K8sOrchestrator) CreateLocalAggregatorServing(aggregator *model.FlAggregator, configFiles map[string]string) error {
	return orch.CreateInfService(common.FL_TYPE_LOCAL_AGGREGATOR, aggregator.Id, configFiles)
}

func (orch *K8sOrchestrator) RemoveLocalAggregatorServing(aggregator *model.FlAggregator) error {
	return orch.RemoveInfService(aggregator.Id)
}

func (orch *K8sOrchestrator) CreateFlClientServing(client *model.FlClient, configFiles map[string]string) error {
	return orch.CreateInfService(common.FL_TYPE_CLIENT, client.Id, configFiles)
}

func (orch *K8sOrchestrator) RemoveFlClientServing(client *model.FlClient) error {
	return orch.RemoveInfService(client.Id)
}
