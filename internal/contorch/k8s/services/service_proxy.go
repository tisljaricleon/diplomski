package k8sorch

import (
	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	intstr "k8s.io/apimachinery/pkg/util/intstr"
)

func BuildInfProxyService(nodeId string, nodePort int32) *corev1.Service {
	servicePort := corev1.ServicePort{
		Port:       common.INF_PROXY_PORT,
		TargetPort: intstr.FromInt(common.INF_PROXY_PORT),
	}
	servicePort.NodePort = nodePort

	return &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{Name: common.GetInfProxySvcName(nodeId)},
		Spec: corev1.ServiceSpec{
			Type: corev1.ServiceTypeNodePort,
			Selector: map[string]string{
				"fl": "proxy-" + nodeId,
			},
			Ports: []corev1.ServicePort{servicePort},
		},
	}
}