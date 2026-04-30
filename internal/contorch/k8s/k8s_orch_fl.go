package k8sorch

import (
	"bytes"
	"context"
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	k8sdeployments "github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/contorch/k8s/deployments"
	k8spv "github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/contorch/k8s/persistant_volumes"
	k8sservices "github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/contorch/k8s/services"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// FL node resources
type flNodeResourceNames struct {
	depName       string
	svcName       string
	configMapName string
	pvName        string
	pvcName       string
}


func (orch *K8sOrchestrator) getNodeRuntime(nodeId string) (string, bool, error) {
	node, exists := orch.availableNodes[nodeId]
	if !exists {
		return "", false, fmt.Errorf("node %s not found in available nodes", nodeId)
	}

	imageType := node.Labels.Common.ImageType
	if imageType == "" {
		return "", false, fmt.Errorf("node %s has no image type label", nodeId)
	}

	image, err := getFlImage(imageType)
	if err != nil {
		return "", false, err
	}

	useMPS := node.Labels.Common.UseMPS
	return image, useMPS, nil
}

func getFlNodeResourceNames(nodeType string, nodeId string) (flNodeResourceNames, error) {
	switch nodeType {
	case common.FL_TYPE_GLOBAL_AGGREGATOR:
		return flNodeResourceNames{
			depName:       common.GetGlAggDepName(nodeId),
			svcName:       common.GetGlAggSvcName(nodeId),
			configMapName: common.GetGlAggConfigMapName(nodeId),
			pvName:        common.GetGlAggPVName(nodeId),
			pvcName:       common.GetGlAggPVCName(nodeId),
		}, nil
	case common.FL_TYPE_LOCAL_AGGREGATOR:
		return flNodeResourceNames{
			depName:       common.GetLocAggDepName(nodeId),
			svcName:       common.GetLocAggSvcName(nodeId),
			configMapName: common.GetLocAggConfigMapName(nodeId),
			pvName:        common.GetLocAggPVName(nodeId),
			pvcName:       common.GetLocAggPVCName(nodeId),
		}, nil
	case common.FL_TYPE_CLIENT:
		return flNodeResourceNames{
			depName:       common.GetClientDepName(nodeId),
			configMapName: common.GetClientConfigMapName(nodeId),
			pvName:        common.GetClientPVName(nodeId),
			pvcName:       common.GetClientPVCName(nodeId),
		}, nil
	default:
		return flNodeResourceNames{}, fmt.Errorf("Unsupported FL node type: %s", nodeType)
	}
}

func (orch *K8sOrchestrator) createFlNode(nodeType string, nodeId string, configFiles map[string]string,
	aggregator *model.FlAggregator, client *model.FlClient) error {
	names, err := getFlNodeResourceNames(nodeType, nodeId)
	if err != nil {
		return err
	}

	image, useMPS, err := orch.getNodeRuntime(nodeId)
	if err != nil {
		return err
	}

	var deployment *appsv1.Deployment
	var service *corev1.Service

	switch nodeType {
	case common.FL_TYPE_GLOBAL_AGGREGATOR:
		if aggregator == nil {
			return fmt.Errorf("Aggregator is required for node type %s", nodeType)
		}
		deployment = k8sdeployments.BuildGlobalAggregatorDeployment(aggregator, orch.namespace, image, useMPS)
		service = k8sservices.BuildAggregatorService(common.FL_TYPE_GLOBAL_AGGREGATOR, aggregator)

	case common.FL_TYPE_LOCAL_AGGREGATOR:
		if aggregator == nil {
			return fmt.Errorf("Aggregator is required for node type %s", nodeType)
		}
		deployment = k8sdeployments.BuildLocalAggregatorDeployment(aggregator, orch.namespace, image, useMPS)
		service = k8sservices.BuildAggregatorService(common.FL_TYPE_LOCAL_AGGREGATOR, aggregator)

	case common.FL_TYPE_CLIENT:
		if client == nil {
			return fmt.Errorf("Client is required for node type %s", nodeType)
		}
		deployment = k8sdeployments.BuildClientDeployment(client, orch.namespace, image, useMPS)

	default:
		return fmt.Errorf("unsupported FL node type: %s", nodeType)
	}

	err = orch.createConfigMapFromFiles(names.configMapName, configFiles)
	if err != nil {
		return err
	}

	pvc := k8spv.BuildPVC(names.pvcName, orch.namespace, common.PVC_STORAGE_SIZE)
	err = orch.createPersistentVolumeClaim(pvc)
	if err != nil {
		return err
	}

	pvPath := common.GetPVPath(nodeId)
	pv := k8spv.BuildPV(
		names.pvName,
		orch.namespace,
		common.PVC_STORAGE_SIZE,
		names.pvcName,
		pvPath,
	)
	err = orch.createPersistentVolume(pv)
	if err != nil {
		return err
	}

	deployment.Spec.Template.Spec.NodeName = nodeId
	err = orch.createDeployment(deployment)
	if err != nil {
		return err
	}

	if service != nil {
		err = orch.createService(service)
		if err != nil {
			return err
		}
	}

	return nil
}

func (orch *K8sOrchestrator) removeFlNode(nodeType string, nodeId string) error {
	names, err := getFlNodeResourceNames(nodeType, nodeId)
	if err != nil {
		return err
	}

	if names.svcName != "" {
		err = orch.deleteService(names.svcName)
		if err != nil {
			return err
		}
	}

	err = orch.deleteDeployment(names.depName)
	if err != nil {
		return err
	}

	err = orch.deleteConfigMap(names.configMapName)
	if err != nil {
		return err
	}

	err = orch.deletePersistentVolumeClaim(names.pvcName, orch.namespace)
	if err != nil {
		return err
	}

	err = orch.deletePersistentVolume(names.pvName)
	if err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) CreateGlAgg(aggregator *model.FlAggregator, configFiles map[string]string) error {
	return orch.createFlNode(common.FL_TYPE_GLOBAL_AGGREGATOR, aggregator.Id, configFiles, aggregator, nil)
}

func (orch *K8sOrchestrator) RemoveGlAgg(aggregator *model.FlAggregator) error {
	return orch.removeFlNode(common.FL_TYPE_GLOBAL_AGGREGATOR, aggregator.Id)
}

func (orch *K8sOrchestrator) CreateLocAgg(aggregator *model.FlAggregator, configFiles map[string]string) error {
	return orch.createFlNode(common.FL_TYPE_LOCAL_AGGREGATOR, aggregator.Id, configFiles, aggregator, nil)
}

func (orch *K8sOrchestrator) RemoveLocAgg(aggregator *model.FlAggregator) error {
	return orch.removeFlNode(common.FL_TYPE_LOCAL_AGGREGATOR, aggregator.Id)
}

func (orch *K8sOrchestrator) CreateClient(client *model.FlClient, configFiles map[string]string) error {
	return orch.createFlNode(common.FL_TYPE_CLIENT, client.Id, configFiles, nil, client)
}

func (orch *K8sOrchestrator) RemoveClient(client *model.FlClient) error {
	return orch.removeFlNode(common.FL_TYPE_CLIENT, client.Id)
}

func (orch *K8sOrchestrator) GetGlAggLogs(aggregatorId string) (bytes.Buffer, error) {
	deployment, err := orch.clientset.AppsV1().Deployments(orch.namespace).Get(context.TODO(),
		common.GetGlAggDepName(aggregatorId), metav1.GetOptions{})
	if err != nil {
		return bytes.Buffer{}, fmt.Errorf("error retrieving deployment: %v", err)
	}

	labelSelector := metav1.FormatLabelSelector(deployment.Spec.Selector)

	podList, err := orch.clientset.CoreV1().Pods(orch.namespace).List(context.TODO(), metav1.ListOptions{
		LabelSelector: labelSelector,
	})
	if err != nil {
		return bytes.Buffer{}, fmt.Errorf("error listing pods: %v", err)
	}

	req := orch.clientset.CoreV1().Pods(orch.namespace).GetLogs(podList.Items[0].Name, &corev1.PodLogOptions{})
	logs, err := req.Stream(context.TODO())
	if err != nil {
		return bytes.Buffer{}, err
	}
	defer logs.Close()

	var buf bytes.Buffer
	_, err = buf.ReadFrom(logs)
	if err != nil {
		return bytes.Buffer{}, err
	}

	return buf, nil
}

func (orch *K8sOrchestrator) GetLocAggLogs(aggregatorId string) (bytes.Buffer, error) {
	deployment, err := orch.clientset.AppsV1().Deployments(orch.namespace).Get(context.TODO(),
		common.GetLocAggDepName(aggregatorId), metav1.GetOptions{})
	if err != nil {
		return bytes.Buffer{}, fmt.Errorf("error retrieving deployment: %v", err)
	}

	labelSelector := metav1.FormatLabelSelector(deployment.Spec.Selector)

	podList, err := orch.clientset.CoreV1().Pods(orch.namespace).List(context.TODO(), metav1.ListOptions{
		LabelSelector: labelSelector,
	})
	if err != nil {
		return bytes.Buffer{}, fmt.Errorf("error listing pods: %v", err)
	}

	req := orch.clientset.CoreV1().Pods(orch.namespace).GetLogs(podList.Items[0].Name, &corev1.PodLogOptions{})
	logs, err := req.Stream(context.TODO())
	if err != nil {
		return bytes.Buffer{}, err
	}
	defer logs.Close()

	var buf bytes.Buffer
	_, err = buf.ReadFrom(logs)
	if err != nil {
		return bytes.Buffer{}, err
	}

	return buf, nil
}

func (orch *K8sOrchestrator) GetClientLogs(clientId string) (bytes.Buffer, error) {
	deployment, err := orch.clientset.AppsV1().Deployments(corev1.NamespaceDefault).Get(context.TODO(),
		common.GetClientDepName(clientId), metav1.GetOptions{})
	if err != nil {
		return bytes.Buffer{}, fmt.Errorf("error retrieving deployment: %v", err)
	}

	labelSelector := metav1.FormatLabelSelector(deployment.Spec.Selector)

	podList, err := orch.clientset.CoreV1().Pods(corev1.NamespaceDefault).List(context.TODO(), metav1.ListOptions{
		LabelSelector: labelSelector,
	})
	if err != nil {
		return bytes.Buffer{}, fmt.Errorf("error listing pods: %v", err)
	}

	req := orch.clientset.CoreV1().Pods(corev1.NamespaceDefault).GetLogs(podList.Items[0].Name, &corev1.PodLogOptions{})
	logs, err := req.Stream(context.TODO())
	if err != nil {
		return bytes.Buffer{}, err
	}
	defer logs.Close()

	var buf bytes.Buffer
	_, err = buf.ReadFrom(logs)
	if err != nil {
		return bytes.Buffer{}, err
	}

	return buf, nil
}
