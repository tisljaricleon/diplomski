package model

type Node struct {
	Id         string
	InternalIp string
	Resources  NodeResources
	Labels     NodeLabels
}

type NodeResources struct {
	CpuTotal float64
	RamTotal float64
	CpuUsage float64
	RamUsage float64
}

type NodeLabels struct {
	Common   CommonLabels
	Fl       FlLabels
	InfProxy InfProxyLabels
}

type CommonLabels struct {
	ImageType string
	UseMPS    bool
}

type FlLabels struct {
	Type               string
	PartitionId        int32
	NumPartitions      int32
	EnergyCost         float32
	CommunicationCosts map[string]float32
	DataDistribution   map[string]int64
}

type InfProxyLabels struct {
	NodePort int32
}
