package server

import (
	"encoding/json"
	"io"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/florch/cost"
)

func toJSON(i interface{}, w io.Writer) error {
	e := json.NewEncoder(w)
	return e.Encode(i)
}

func fromJSON(i interface{}, r io.Reader) error {
	d := json.NewDecoder(r)
	return d.Decode(i)
}

type StartFlRequest struct {
	TrainingParams      TrainingParams         `json:"trainingParams"`
	InferenceParams     InferenceParams        `json:"inferenceParams"`
	ModelSize           float32                `json:"modelSize"`
	CostSource          cost.CostSource        `json:"costSource"`
	CostConfiguration   cost.CostConfiguration `json:"costConfiguration"`
	ConfigurationModel  string                 `json:"configurationModel"`
	RvaEnabled          bool                   `json:"rvaEnabled"`
}

type TrainingParams struct {
	Epochs              int32   `json:"epochs"`
	LocalRounds         int32   `json:"localRounds"`
	GlobalRounds        int32   `json:"globalRounds"`
	MinFitClients       int32   `json:"minFitClients"`
	MinEvaluateClients  int32   `json:"minEvaluateClients"`
	MinAvailableClients int32   `json:"minAvailableClients"`
	BatchSize           int32   `json:"batchSize"`
	LearningRate        float32 `json:"learningRate"`
}

type InferenceParams struct {
	EnableServing bool `json:"enableServing"`
}
