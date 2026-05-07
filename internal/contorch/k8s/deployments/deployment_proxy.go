package k8sorch

import (
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func BuildInfProxyDeployment(nodeId, namespace, image, localServiceURL, parentServiceURL string) *appsv1.Deployment {
	labelValue := "proxy-" + nodeId
	volumeMounts := []corev1.VolumeMount{{
		Name:      "proxyconfig",
		MountPath: "/etc/nginx",
		ReadOnly:  true,
	}}
	volumes := []corev1.Volume{{
		Name: "proxyconfig",
		VolumeSource: corev1.VolumeSource{ConfigMap: &corev1.ConfigMapVolumeSource{
			LocalObjectReference: corev1.LocalObjectReference{Name: common.GetInfProxyConfigMapName(nodeId)},
			Items: []corev1.KeyToPath{
				{Key: "nginx.conf", Path: "nginx.conf"},
				{Key: "proxy.lua", Path: "lua/proxy.lua"},
			},
		}},
	}}
	env := []corev1.EnvVar{
		{Name: "LOCAL_SERVICE_URL", Value: localServiceURL},
		{Name: "PARENT_SERVICE_URL", Value: parentServiceURL},
		{Name: "MAX_INFLIGHT", Value: "200"},
	}

	return &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      common.GetInfProxyDepName(nodeId),
			Namespace: namespace,
		},
		Spec: appsv1.DeploymentSpec{
			Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"fl": labelValue}},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"fl": labelValue}},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{{
						Name:         "inf-proxy",
						Image:        image,
						Ports: []corev1.ContainerPort{
							{ContainerPort: common.INF_PROXY_PORT},
							{ContainerPort: common.INF_PROXY_SIDECAR_PORT},
						},
						VolumeMounts: volumeMounts,
						Env:          env,
						Resources: corev1.ResourceRequirements{
							Requests: corev1.ResourceList{
								corev1.ResourceCPU:    resource.MustParse("50m"),
								corev1.ResourceMemory: resource.MustParse("64Mi"),
							},
							Limits: corev1.ResourceList{
								corev1.ResourceCPU:    resource.MustParse("250m"),
								corev1.ResourceMemory: resource.MustParse("256Mi"),
							},
						},
					}},
					Volumes: volumes,
				},
			},
		},
	}
}