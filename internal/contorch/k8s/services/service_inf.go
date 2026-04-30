package k8sorch

import (
	"fmt"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/common"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	intstr "k8s.io/apimachinery/pkg/util/intstr"
)

func BuildInfServiceService(nodeId string) *corev1.Service {
	return &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{Name: common.GetInfSvcSvcName(nodeId)},
		Spec: corev1.ServiceSpec{
			Type: corev1.ServiceTypeNodePort,
			Selector: map[string]string{
				"fl": fmt.Sprintf("serving-%s", nodeId),
			},
			Ports: []corev1.ServicePort{{
				Port:       common.INF_SERVICE_PORT,
				TargetPort: intstr.FromInt(common.INF_SERVICE_PORT),
			}},
		},
	}
}
