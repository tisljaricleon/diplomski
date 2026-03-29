package k8sorch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func BuildGlobalAggregatorDeployment(aggregator *model.FlAggregator, namespace string) *appsv1.Deployment {
       deployment := &appsv1.Deployment{
	       ObjectMeta: metav1.ObjectMeta{
		       Name:      common.GetGlobalAggregatorDeploymentName(aggregator.Id),
		       Namespace: namespace,
	       },
		Spec: appsv1.DeploymentSpec{
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"fl": "ga",
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"fl": "ga",
					},
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{
							Name:  "fl-ga",
							Image: common.GLOBAL_AGGRETATOR_IMAGE,
							Ports: []corev1.ContainerPort{
								{
									ContainerPort: aggregator.Port,
								},
							},
							VolumeMounts: []corev1.VolumeMount{
								{
									Name:      "gaconfig",
									MountPath: "/home/task.py",
									SubPath:   "task.py",
								},
								{
									Name:      "gaconfig",
									MountPath: "/home/global_server.py",
									SubPath:   "global_server.py",
								},
								{
									Name:      "gaconfig",
									MountPath: "/home/global_server_config.yaml",
									SubPath:   "global_server_config.yaml",
								},
								{
									Name:      "modelstorage",
									MountPath: "/home/model",
								},
							},
							Resources: corev1.ResourceRequirements{
								Requests: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("1.0"),
									corev1.ResourceMemory: resource.MustParse("1500Mi"),
								},
								Limits: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("2.0"),
									corev1.ResourceMemory: resource.MustParse("2000Mi"),
								},
							},
						},
					},
					Volumes: []corev1.Volume{
						{
							Name: "gaconfig",
							VolumeSource: corev1.VolumeSource{
								ConfigMap: &corev1.ConfigMapVolumeSource{
									Items: []corev1.KeyToPath{},
									LocalObjectReference: corev1.LocalObjectReference{
										Name: common.GetGlobalAggregatorConfigMapName(aggregator.Id),
									},
								},
							},
						},
						{
							Name: "modelstorage",
							VolumeSource: corev1.VolumeSource{
								PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
									ClaimName: common.GetGlobalAggregatorPersistentVolumeClaimName(aggregator.Id),
								},
							},
						},
					},
				},
			},
		},
	}

	return deployment
}

func BuildLocalAggregatorDeployment(aggregator *model.FlAggregator, namespace string) *appsv1.Deployment {
       deployment := &appsv1.Deployment{
	       ObjectMeta: metav1.ObjectMeta{
		       Name:      common.GetLocalAggregatorDeploymentName(aggregator.Id),
		       Namespace: namespace,
	       },
		Spec: appsv1.DeploymentSpec{
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"fl": fmt.Sprintf("la-%s", aggregator.Id),
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"fl": fmt.Sprintf("la-%s", aggregator.Id),
					},
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{
							Name:  "fl-la",
							Image: common.LOCAL_AGGRETATOR_IMAGE,
							Ports: []corev1.ContainerPort{
								{
									ContainerPort: aggregator.Port,
								},
							},
							VolumeMounts: []corev1.VolumeMount{
								{
									Name:      "laconfig",
									MountPath: "/home/local_server_config.yaml",
									SubPath:   "local_server_config.yaml",
								},
								{
									Name:      "modelstorage",
									MountPath: "/home/model",
								},
							},
							Resources: corev1.ResourceRequirements{
								Requests: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("1.0"),
									corev1.ResourceMemory: resource.MustParse("1500Mi"),
								},
								Limits: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("2.0"),
									corev1.ResourceMemory: resource.MustParse("2000Mi"),
								},
							},
						},
					},
					Volumes: []corev1.Volume{
						{
							Name: "laconfig",
							VolumeSource: corev1.VolumeSource{
								ConfigMap: &corev1.ConfigMapVolumeSource{
									Items: []corev1.KeyToPath{},
									LocalObjectReference: corev1.LocalObjectReference{
										Name: common.GetLocalAggregatorConfigMapName(aggregator.Id),
									},
								},
							},
						},
						{
							Name: "modelstorage",
							VolumeSource: corev1.VolumeSource{
								PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
									ClaimName: common.GetLocalAggregatorPersistentVolumeClaimName(aggregator.Id),
								},
							},
						},
					},
				},
			},
		},
	}

	return deployment
}

func BuildClientDeployment(client *model.FlClient, namespace string) *appsv1.Deployment {
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      common.GetClientDeploymentName(client.Id),
			Namespace: namespace,
		},
		Spec: appsv1.DeploymentSpec{
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"fl": fmt.Sprintf("client-%s", client.Id),
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"fl": fmt.Sprintf("client-%s", client.Id),
					},
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{
							Name:  "fl-client",
							Image: common.FL_CLIENT_IMAGE,
							VolumeMounts: []corev1.VolumeMount{
								{
									Name:      "clientconfig",
									MountPath: "/home/task.py",
									SubPath:   "task.py",
								},
								{
									Name:      "clientconfig",
									MountPath: "/home/client.py",
									SubPath:   "client.py",
								},
								{
									Name:      "clientconfig",
									MountPath: "/home/client_config.yaml",
									SubPath:   "client_config.yaml",
								},
								{
									Name:      "modelstorage",
									MountPath: "/home/model",
								},
							},
							Resources: corev1.ResourceRequirements{
								Requests: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("1.0"),
									corev1.ResourceMemory: resource.MustParse("1500Mi"),
								},
								Limits: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("2.0"),
									corev1.ResourceMemory: resource.MustParse("2000Mi"),
								},
							},
						},
					},
					Volumes: []corev1.Volume{
						{
							Name: "clientconfig",
							VolumeSource: corev1.VolumeSource{
								ConfigMap: &corev1.ConfigMapVolumeSource{
									Items: []corev1.KeyToPath{},
									LocalObjectReference: corev1.LocalObjectReference{
										Name: common.GetClientConfigMapName(client.Id),
									},
								},
							},
						},
						{
							Name: "modelstorage",
							VolumeSource: corev1.VolumeSource{
								PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
									ClaimName: common.GetClientPersistentVolumeClaimName(client.Id),
								},
							},
						},
					},
				},
			},
		},
	}

	return deployment
}

func BuildGlobalAggregatorServingDeployment(aggregator *model.FlAggregator, namespace string) *appsv1.Deployment {
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      common.GetGlobalAggregatorServingDeploymentName(aggregator.Id),
			Namespace: namespace,
		},
		Spec: appsv1.DeploymentSpec{
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"fl": fmt.Sprintf("serving-%s", aggregator.Id),
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"fl": fmt.Sprintf("serving-%s", aggregator.Id),
					},
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{
							Name:  "fl-serving",
							Image: common.GLOBAL_AGGREGATOR_SERVING_IMAGE,
							Ports: []corev1.ContainerPort{
								{ ContainerPort: common.GLOBAL_AGGREGATOR_SERVING_PORT },
								
							},
							VolumeMounts: []corev1.VolumeMount{
								{
									Name:      "servingconfig",
									MountPath: "/home/global_server_serving_config.yaml",
									SubPath:   "global_server_serving_config.yaml",
								},
								{
									Name:      "modelstorage",
									MountPath: "/home/model",
								},
								
							},
							Resources: corev1.ResourceRequirements{
								Requests: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("0.2"),
									corev1.ResourceMemory: resource.MustParse("256Mi"),
								},
								Limits: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("1.0"),
									corev1.ResourceMemory: resource.MustParse("1Gi"),
								},
							},
						},
					},
					Volumes: []corev1.Volume{
						{
							Name: "servingconfig",
							VolumeSource: corev1.VolumeSource{
								ConfigMap: &corev1.ConfigMapVolumeSource{
									Items: []corev1.KeyToPath{},
									LocalObjectReference: corev1.LocalObjectReference{
										Name: common.GetGlobalAggregatorServingConfigMapName(aggregator.Id),
									},
								},
							},
						},
						{
							Name: "modelstorage",
							VolumeSource: corev1.VolumeSource{
								PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
									ClaimName: common.GetGlobalAggregatorPersistentVolumeClaimName(aggregator.Id),
								},
							},
						},

					},
				},
			},
		},
	}
	return deployment
}

func BuildClientServingDeployment(client *model.FlClient, namespace string) *appsv1.Deployment {
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      common.GetClientServingDeploymentName(client.Id),
			Namespace: namespace,
		},
		Spec: appsv1.DeploymentSpec{
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"fl": fmt.Sprintf("serving-%s", client.Id),
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"fl": fmt.Sprintf("serving-%s", client.Id),
					},
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{
							Name:  "fl-serving",
							Image: common.CLIENT_SERVING_IMAGE,
							Ports: []corev1.ContainerPort{
								{ ContainerPort: common.FL_CLIENT_SERVING_PORT },
								
							},
							   VolumeMounts: []corev1.VolumeMount{
								   {
									   Name:      "servingconfig",
									   MountPath: "/home/client_serving.py",
									   SubPath:   "client_serving.py",
								   },
								   {
									   Name:      "servingconfig",
									   MountPath: "/home/client_serving_config.yaml",
									   SubPath:   "client_serving_config.yaml",
								   },
								   {
									   Name:      "modelstorage",
									   MountPath: "/home/model",
								   },
								   {
									   Name:      "tegrastats-bin",
									   MountPath: "/usr/bin/tegrastats",
									   ReadOnly:  true,
								   },
							   },
							Resources: corev1.ResourceRequirements{
								Requests: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("0.2"),
									corev1.ResourceMemory: resource.MustParse("256Mi"),
								},
								Limits: corev1.ResourceList{
									corev1.ResourceCPU:    resource.MustParse("1.0"),
									corev1.ResourceMemory: resource.MustParse("1Gi"),
								},
							},
						},
					},
					Volumes: []corev1.Volume{
						{
							Name: "servingconfig",
							VolumeSource: corev1.VolumeSource{
								ConfigMap: &corev1.ConfigMapVolumeSource{
									Items: []corev1.KeyToPath{},
									LocalObjectReference: corev1.LocalObjectReference{
										Name: common.GetClientServingConfigMapName(client.Id),
									},
								},
							},
						},
						{
							Name: "modelstorage",
							VolumeSource: corev1.VolumeSource{
								PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
									ClaimName: common.GetClientPersistentVolumeClaimName(client.Id),
								},
							},
						},
						{
							Name: "tegrastats-bin",
							VolumeSource: corev1.VolumeSource{
								HostPath: &corev1.HostPathVolumeSource{
									Path: "/usr/bin/tegrastats",
									Type: &corev1.HostPathFile,
								},
							},
						},
					},
				},
			},
		},
	}
	return deployment
}