package k8sorch

import (
	"context"
	"fmt"
	"log"
	"strconv"
	"strings"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/events"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
	"github.com/robfig/cron/v3"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/metrics/pkg/apis/metrics/v1beta1"
	metricsv "k8s.io/metrics/pkg/client/clientset/versioned"
)

type K8sOrchestrator struct {
	config             *rest.Config
	clientset          *kubernetes.Clientset
	metricsClientset   *metricsv.Clientset
	eventBus           *events.EventBus
	cronScheduler      *cron.Cron
	availableNodes     map[string]*model.Node
	namespace          string
}

func NewK8sOrchestrator(configFilePath string, eventBus *events.EventBus, namespace string) (*K8sOrchestrator, error) {
	config, err := clientcmd.BuildConfigFromFlags("", configFilePath)
	if err != nil {
		log.Println(err.Error())
		return nil, err
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		log.Println(err.Error())
		return nil, err
	}

	metricsClientset, err := metricsv.NewForConfig(config)
	if err != nil {
		log.Println(err.Error())
		return nil, err
	}

	   return &K8sOrchestrator{
		   config:           config,
		   clientset:        clientset,
		   metricsClientset: metricsClientset,
		   eventBus:         eventBus,
		   cronScheduler:    cron.New(cron.WithSeconds()),
		   availableNodes:   make(map[string]*model.Node),
		   namespace:        namespace,
	   }, nil
}

func (orch *K8sOrchestrator) GetAvailableNodes(initialRequest bool) (map[string]*model.Node, error) {
	nodesCoreList, err := orch.clientset.CoreV1().Nodes().List(context.Background(), metav1.ListOptions{})
	if err != nil {
		log.Println("Failed to retrieve nodes on node status")
		return nil, err
	}

	nodeMetricsList, err := orch.metricsClientset.MetricsV1beta1().NodeMetricses().List(context.Background(), metav1.ListOptions{})
	if err != nil {
		log.Println("Failed to retrieve node metrices on node status")
		return nil, err
	}

	nodeMetricsMap := make(map[string]v1beta1.NodeMetrics)
	for _, nodeMetric := range nodeMetricsList.Items {
		nodeMetricsMap[nodeMetric.Name] = nodeMetric
	}

	nodes := make(map[string]*model.Node)
	for _, nodeCore := range nodesCoreList.Items {
		nodeMetric, exists := nodeMetricsMap[nodeCore.Name]
		if !exists {
			continue
		}

		if !isNodeReady(nodeCore) {
			continue
		}

		nodeModel := nodeCoreToNodeModel(nodeCore, nodeMetric)
		if nodeModel == nil {
			continue
		}

		nodes[nodeModel.Id] = nodeModel

		if initialRequest {
			orch.availableNodes[nodeModel.Id] = nodeModel
		}
	}

	return nodes, nil
}

func nodeCoreToNodeModel(nodeCore corev1.Node, nodeMetric v1beta1.NodeMetrics) *model.Node {
	cpuUsage := nodeMetric.Usage[corev1.ResourceCPU]
	cpuPercentage := float64(cpuUsage.MilliValue()) / float64(nodeCore.Status.Capacity.Cpu().MilliValue())

	memoryUsage := nodeMetric.Usage[corev1.ResourceMemory]
	memoryPercentage := float64(memoryUsage.Value()) / float64(nodeCore.Status.Capacity.Memory().Value())

	hostIP := getHostIp(nodeCore)

	nodeModel := &model.Node{
		Id:         nodeCore.Name,
		InternalIp: hostIP,
		Resources: model.NodeResources{
			CpuUsage: cpuPercentage,
			RamUsage: memoryPercentage,
		},
	}

	nodeLabelsToNodeModel(nodeCore.Labels, nodeModel)

	if nodeModel.Labels.Fl.Type == "" {
		return nil
	}

	return nodeModel
}

func nodeLabelsToNodeModel(labels map[string]string, nodeModel *model.Node) {
		flType := labels[common.FlTypeLabel]
		numPartitions, _ := strconv.Atoi(labels[common.NumPartitionsLabel])
		partitionId, _ := strconv.Atoi(labels[common.PartitionIdLabel])
		imageType := labels[common.ImageTypeLabel]
		useMPS := labels[common.UseMPSLabel] == "true"
		proxyNodePort, _ := strconv.Atoi(labels[common.ProxyNodePortLabel])

		communicationCosts := make(map[string]float32)
		dataDistribution := make(map[string]int64)
		for key, value := range labels {
			if strings.HasPrefix(key, common.CommunicationCostPrefix) {
				splits := strings.Split(key, common.CommunicationCostPrefix)
				if len(splits) == 2 {
					cost, _ := strconv.ParseFloat(value, 32)
					communicationCosts[splits[1]] = float32(cost)
				}
			} else if strings.HasPrefix(key, common.DataDistributionPrefix) {
				splits := strings.Split(key, common.DataDistributionPrefix)
				if len(splits) == 2 {
					numberOfSamples, _ := strconv.Atoi(value)
					dataDistribution[splits[1]] = int64(numberOfSamples)
				}
			}
		}

		nodeModel.Labels.Fl.Type = flType
		nodeModel.Labels.Fl.PartitionId = int32(partitionId)
		nodeModel.Labels.Fl.NumPartitions = int32(numPartitions)
		nodeModel.Labels.Fl.EnergyCost = 0.0
		nodeModel.Labels.Fl.CommunicationCosts = communicationCosts
		nodeModel.Labels.Fl.DataDistribution = dataDistribution
		nodeModel.Labels.Common.ImageType = imageType
		nodeModel.Labels.Common.UseMPS = useMPS
		nodeModel.Labels.InfProxy.NodePort = int32(proxyNodePort)
}

// Event notifiers
func (orch *K8sOrchestrator) StartNodeStateChangeNotifier() {
	orch.cronScheduler.AddFunc("@every 1s", orch.notifyNodeStateChanges)

	orch.cronScheduler.Start()
}

func (orch *K8sOrchestrator) StopAllNotifiers() {
	orch.cronScheduler.Stop()
}

func (orch *K8sOrchestrator) notifyNodeStateChanges() {
	availableNodesNew, err := orch.GetAvailableNodes(false)
	if err != nil {
		return
	}

	event := common.GetNodeStateChangeEvent(orch.availableNodes, availableNodesNew)
	if (event != events.Event{}) {
		orch.eventBus.Publish(event)
	}

	orch.availableNodes = availableNodesNew
}


// Create Kubernetes resources
func (orch *K8sOrchestrator) createConfigMapFromFiles(configMapName string, filesData map[string]string) error {
	configMapsClient := orch.clientset.CoreV1().ConfigMaps(orch.namespace)

	cm := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      configMapName,
			Namespace: orch.namespace,
		},
		Data: filesData,
	}

	_, err := configMapsClient.Create(context.TODO(), cm, metav1.CreateOptions{})
	if err != nil {
		fmt.Printf("Error creating ConfigMap: %v\n", err)
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) deleteConfigMap(configMapName string) error {
	configMapsClient := orch.clientset.CoreV1().ConfigMaps(orch.namespace)

	if err := configMapsClient.Delete(context.TODO(), configMapName, metav1.DeleteOptions{}); err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) createDeployment(deployment *appsv1.Deployment) error {
	deploymentsClient := orch.clientset.AppsV1().Deployments(orch.namespace)

	_, err := deploymentsClient.Create(context.TODO(), deployment, metav1.CreateOptions{})

	return err
}

func (orch *K8sOrchestrator) deleteDeployment(deploymentName string) error {
	deploymentsClient := orch.clientset.AppsV1().Deployments(orch.namespace)

	if err := deploymentsClient.Delete(context.TODO(), deploymentName, metav1.DeleteOptions{}); err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) createService(service *corev1.Service) error {
	servicesClient := orch.clientset.CoreV1().Services(orch.namespace)

	_, err := servicesClient.Create(context.TODO(), service, metav1.CreateOptions{})
	if err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) deleteService(serviceName string) error {
	servicesClient := orch.clientset.CoreV1().Services(orch.namespace)

	err := servicesClient.Delete(context.TODO(), serviceName, metav1.DeleteOptions{}); 
	if err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) createPersistentVolume(pv *corev1.PersistentVolume) error {
	persistantVolumesClient := orch.clientset.CoreV1().PersistentVolumes()

	_, err := persistantVolumesClient.Create(context.TODO(), pv, metav1.CreateOptions{})

	if err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) deletePersistentVolume(pvName string) error {
	persistantVolumesClient := orch.clientset.CoreV1().PersistentVolumes()

	err := persistantVolumesClient.Delete(context.TODO(), pvName, metav1.DeleteOptions{})
	if err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) createPersistentVolumeClaim(pvc *corev1.PersistentVolumeClaim) error {
	persistentVolumeClaimsClient := orch.clientset.CoreV1().PersistentVolumeClaims(orch.namespace)

	_, err := persistentVolumeClaimsClient.Create(context.TODO(), pvc, metav1.CreateOptions{})
	if err != nil {
		return err
	}

	return nil
}

func (orch *K8sOrchestrator) deletePersistentVolumeClaim(pvcName, pvcNamespace string) error {
	persistentVolumeClaimsClient := orch.clientset.CoreV1().PersistentVolumeClaims(pvcNamespace)

	err := persistentVolumeClaimsClient.Delete(context.TODO(), pvcName, metav1.DeleteOptions{})
	if err != nil {
		return err
	}

	return nil
}

// Helper functions
func isNodeReady(nodeCore corev1.Node) bool {
	for _, condition := range nodeCore.Status.Conditions {
		if condition.Type == "Ready" {
			if condition.Status == "True" {
				return true
			} else {
				return false
			}
		}
	}

	return false
}

func getFlType(labels map[string]string) string {
	flType := labels[common.FlTypeLabel]
	return flType
}

func getCommCostsAndDataDistribution(labels map[string]string) (map[string]float32, map[string]int64) {
	communicationCosts := make(map[string]float32)
	dataDistribution := make(map[string]int64)
	for key, value := range labels {
		if strings.HasPrefix(key, common.CommunicationCostPrefix) {
			splits := strings.Split(key, common.CommunicationCostPrefix)
			if len(splits) == 2 {
				cost, _ := strconv.ParseFloat(value, 32)
				communicationCosts[splits[1]] = float32(cost)
			}
		} else if strings.HasPrefix(key, common.DataDistributionPrefix) {
			splits := strings.Split(key, common.DataDistributionPrefix)
			if len(splits) == 2 {
				numberOfSamples, _ := strconv.Atoi(value)
				dataDistribution[splits[1]] = int64(numberOfSamples)
			}
		}
	}

	return communicationCosts, dataDistribution
}

func getHostIp(node corev1.Node) string {
	for _, val := range node.Status.Addresses {
		if val.Type == corev1.NodeInternalIP {
			return val.Address
		}
	}

	return ""
}

