package k8sorch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func BuildInfServiceDeployment(nodeId, pvcClaimName, namespace, image string, useMPS bool) *appsv1.Deployment {
	labelValue := fmt.Sprintf("serving-%s", nodeId)

	volumeMounts := []corev1.VolumeMount{
		{Name: "servingconfig", MountPath: "/home"},
		{Name: "modelstorage", MountPath: "/home/model"},
	}
	volumes := []corev1.Volume{
		{
			Name: "servingconfig",
			VolumeSource: corev1.VolumeSource{ConfigMap: &corev1.ConfigMapVolumeSource{
				Items:                []corev1.KeyToPath{},
				LocalObjectReference: corev1.LocalObjectReference{Name: common.GetInfSvcConfigMapName(nodeId)},
			}},
		},
		{Name: "modelstorage", VolumeSource: corev1.VolumeSource{PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{ClaimName: pvcClaimName}}},
	}
	env := []corev1.EnvVar{}

	if useMPS {
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
	}

	return &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      common.GetInfSvcDepName(nodeId),
			Namespace: namespace,
		},
		Spec: appsv1.DeploymentSpec{
			Selector: &metav1.LabelSelector{
				MatchLabels: map[string]string{"fl": labelValue},
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"fl": labelValue}},
				Spec: corev1.PodSpec{
					HostIPC: useMPS,
					Containers: []corev1.Container{{
						Name:         "fl-serving",
						Image:        image,
						Ports:        []corev1.ContainerPort{{ContainerPort: common.INF_SERVICE_PORT}},
						VolumeMounts: volumeMounts,
						Env:          env,
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
					}},
					Volumes: volumes,
				},
			},
		},
	}
}
