package model

type FlClient struct {
	Id               string
	ParentAddress    string
	ParentNodeId     string
	Epochs           int32
	DataDistribution map[string]int64
	NumPartitions    int32
	PartitionId      int32
	BatchSize        int32
	LearningRate     float32
	ClientUtility    ClientUtility
}

type FlAggregator struct {
	Id                  string
	InternalAddress     string
	ExternalAddress     string
	ParentAddress       string
	Port                int32
	NumClients          int32
	Rounds              int32
	LocalRounds         int32
	MinFitClients       int32
	MinEvaluateClients  int32
	MinAvailableClients int32
}
