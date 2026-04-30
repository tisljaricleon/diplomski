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

func applyMPSRuntime(useMPS bool, volumeMounts []corev1.VolumeMount, volumes []corev1.Volume) ([]corev1.VolumeMount, []corev1.EnvVar, []corev1.Volume) {
	env := []corev1.EnvVar{}
	if !useMPS {
		return volumeMounts, env, volumes
	}

	volumeMounts = append([]corev1.VolumeMount{
		{Name: "mpspipe", MountPath: "/tmp/nvidia-mps"},
		{Name: "mpslog", MountPath: "/tmp/nvidia-mps-log"},
	}, volumeMounts...)

	volumes = append([]corev1.Volume{
		{Name: "mpspipe", VolumeSource: corev1.VolumeSource{HostPath: &corev1.HostPathVolumeSource{Path: "/tmp/nvidia-mps"}}},
		{Name: "mpslog", VolumeSource: corev1.VolumeSource{HostPath: &corev1.HostPathVolumeSource{Path: "/tmp/nvidia-mps-log"}}},
	}, volumes...)

	env = []corev1.EnvVar{
		{Name: "CUDA_MPS_PIPE_DIRECTORY", Value: "/tmp/nvidia-mps"},
		{Name: "CUDA_MPS_LOG_DIRECTORY", Value: "/tmp/nvidia-mps-log"},
	}

	return volumeMounts, env, volumes
}

func BuildGlobalAggregatorDeployment(aggregator *model.FlAggregator, namespace string, image string, useMPS bool) *appsv1.Deployment {
	volumeMounts, env, volumes := applyMPSRuntime(useMPS,
		[]corev1.VolumeMount{
			{Name: "gaconfig", MountPath: "/home"},
			{Name: "modelstorage", MountPath: "/home/model"},
		},
		[]corev1.Volume{
			{
				Name: "gaconfig",
				VolumeSource: corev1.VolumeSource{
					ConfigMap: &corev1.ConfigMapVolumeSource{
						Items:                []corev1.KeyToPath{},
						LocalObjectReference: corev1.LocalObjectReference{Name: common.GetGlAggConfigMapName(aggregator.Id)},
					},
				},
			},
			{
				Name: "modelstorage",
				VolumeSource: corev1.VolumeSource{
					PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{ClaimName: common.GetGlAggPVCName(aggregator.Id)},
				},
			},
		},
	)

	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      common.GetGlAggDepName(aggregator.Id),
			Namespace: namespace,
		},
		Spec: appsv1.DeploymentSpec{
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{
					"fl": fmt.Sprintf("ga-%s", aggregator.Id),
				},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: map[string]string{
						"fl": fmt.Sprintf("ga-%s", aggregator.Id),
					},
				},
				Spec: corev1.PodSpec{
					HostIPC: useMPS,
					Containers: []corev1.Container{
						{
							Name:  "fl-ga",
							Image: image,
							Ports: []corev1.ContainerPort{
								{ContainerPort: aggregator.Port},
							},
							VolumeMounts: volumeMounts,
							Env:          env,
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
					Volumes: volumes,
				},
			},
		},
	}

	return deployment
}

func BuildLocalAggregatorDeployment(aggregator *model.FlAggregator, namespace string, image string, useMPS bool) *appsv1.Deployment {
	volumeMounts, env, volumes := applyMPSRuntime(useMPS,
		[]corev1.VolumeMount{
			{Name: "laconfig", MountPath: "/home"},
			{Name: "modelstorage", MountPath: "/home/model"},
		},
		[]corev1.Volume{
			{
				Name: "laconfig",
				VolumeSource: corev1.VolumeSource{
					ConfigMap: &corev1.ConfigMapVolumeSource{
						Items:                []corev1.KeyToPath{},
						LocalObjectReference: corev1.LocalObjectReference{Name: common.GetLocAggConfigMapName(aggregator.Id)},
					},
				},
			},
			{
				Name: "modelstorage",
				VolumeSource: corev1.VolumeSource{
					PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{ClaimName: common.GetLocAggPVCName(aggregator.Id)},
				},
			},
		},
	)

	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      common.GetLocAggDepName(aggregator.Id),
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
					HostIPC: useMPS,
					Containers: []corev1.Container{
						{
							Name:  "fl-la",
							Image: image,
							Ports: []corev1.ContainerPort{
								{ContainerPort: aggregator.Port},
							},
							VolumeMounts: volumeMounts,
							Env:          env,
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
					Volumes: volumes,
				},
			},
		},
	}

	return deployment
}

func BuildClientDeployment(client *model.FlClient, namespace string, image string, useMPS bool) *appsv1.Deployment {
	volumeMounts, env, volumes := applyMPSRuntime(useMPS,
		[]corev1.VolumeMount{
			{Name: "clientconfig", MountPath: "/home"},
			{Name: "modelstorage", MountPath: "/home/model"},
		},
		[]corev1.Volume{
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
						ClaimName: common.GetClientPVCName(client.Id),
					},
				},
			},
		},
	)

	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      common.GetClientDepName(client.Id),
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
					HostIPC: useMPS,
					Containers: []corev1.Container{
						{
							Name:         "fl-client",
							Image:        image,
							VolumeMounts: volumeMounts,
							Env:          env,
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
					Volumes: volumes,
				},
			},
		},
	}

	return deployment
}
