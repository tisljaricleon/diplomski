package florch

import (
	"fmt"
	"os"
	"strconv"

	"github.com/AIoTwin-Adaptive-FL-Orch/fl-orchestrator/internal/model"
)

func BuildGlobalAggregatorConfigFiles(flAggregator *model.FlAggregator) (map[string]string, error) {
	configDirectoryPath := "../../configs/fl/"
	buildImagesPath := "../../internal/build_images/global_server/"

	taskBytesArray, err := os.ReadFile(fmt.Sprint(configDirectoryPath, "task/task.py"))
	if err != nil {
		fmt.Print(err)
	}
	taskString := string(taskBytesArray)

	globalsrvBytesArray, err := os.ReadFile(fmt.Sprint(buildImagesPath, "global_server.py"))
	if err != nil {
		fmt.Print(err)
	}
	globalsrvString := string(globalsrvBytesArray)

	globalAggregatorConfig := GlobalAggregatorConfig_Yaml

	filesData := map[string]string{
		"task.py":                   taskString,
		"global_server.py":          globalsrvString,
		"global_server_config.yaml": globalAggregatorConfig,
	}

	return filesData, nil
}

func BuildLocalAggregatorConfigFiles(flAggregator *model.FlAggregator) (map[string]string, error) {
	localAggregatorConfig := fmt.Sprintf(LocalAggregatorConfig_Yaml, flAggregator.ParentAddress, strconv.Itoa(int(flAggregator.LocalRounds)))

	filesData := map[string]string{
		"local_server_config.yaml": localAggregatorConfig,
	}

	return filesData, nil
}

func BuildClientConfigFiles(client *model.FlClient) (map[string]string, error) {
	configDirectoryPath := "../../configs/fl/"
	buildImagesPath := "../../internal/build_images/client/"

	taskBytesArray, err := os.ReadFile(fmt.Sprint(configDirectoryPath, "task/task.py"))
	if err != nil {
		fmt.Print(err)
	}
	taskString := string(taskBytesArray)

	clientpyBytesArray, err := os.ReadFile(fmt.Sprint(buildImagesPath, "client.py"))
	if err != nil {
		fmt.Print(err)
	}
	clientpyString := string(clientpyBytesArray)

	clientConfigString := fmt.Sprintf(ClientConfig_Yaml, client.ParentAddress, strconv.Itoa(int(client.PartitionId)),
		strconv.Itoa(int(client.NumPartitions)), strconv.Itoa(int(client.Epochs)), strconv.Itoa(int(client.BatchSize)),
		fmt.Sprintf("%f", client.LearningRate))

	filesData := map[string]string{
		"task.py":            taskString,
		"client.py":          clientpyString,
		"client_config.yaml": clientConfigString,
	}

	return filesData, nil
}

func BuildGlobalAggregatorServingConfigFiles() (map[string]string, error) {
	buildImagesPath := "../../internal/build_images/global_server_serving/"

	servingpyBytesArray, err := os.ReadFile(fmt.Sprint(buildImagesPath, "serving.py"))
	if err != nil {
		fmt.Print(err)
	}
	servingpyString := string(servingpyBytesArray)

	globalAggregatorServingConfig := GlobalAggregatorServingConfig_Yaml

	filesData := map[string]string{
		"global_server_serving.py":         servingpyString,
		"global_server_serving_config.yaml": globalAggregatorServingConfig,
	}

	return filesData, nil
}

func BuildLocalAggregatorServingConfigFiles() (map[string]string, error) {
	buildImagesPath := "../../internal/build_images/local_server_serving/"

	servingpyBytesArray, err := os.ReadFile(fmt.Sprint(buildImagesPath, "serving.py"))
	if err != nil {
		fmt.Print(err)
	}
	servingpyString := string(servingpyBytesArray)

	localAggregatorServingConfig := LocalAggregatorServingConfig_Yaml

	filesData := map[string]string{
		"local_server_serving.py":         servingpyString,
		"local_server_serving_config.yaml": localAggregatorServingConfig,
	}

	return filesData, nil
}

func BuildClientServingConfigFiles() (map[string]string, error) {
	configDirectoryPath := "../../configs/fl/"
	buildImagesPath := "../../internal/build_images/client_serving/"

	taskBytesArray, err := os.ReadFile(fmt.Sprint(configDirectoryPath, "task/task.py"))
	if err != nil {
		fmt.Print(err)
	}
	taskString := string(taskBytesArray)

	servingpyBytesArray, err := os.ReadFile(fmt.Sprint(buildImagesPath, "client_serving.py"))
	if err != nil {
		fmt.Print(err)
	}
	servingpyString := string(servingpyBytesArray)

	clientServingConfig := ClientServingConfig_Yaml

	filesData := map[string]string{
		"task.py":            taskString,
		"client_serving.py":         servingpyString,
		"client_serving_config.yaml": clientServingConfig,
	}

	return filesData, nil
}


const GlobalAggregatorConfig_Yaml = `
server:
  address: "0.0.0.0:8080"
  global_rounds: 40

strategy:
  fraction_fit: 1.0
  fraction_evaluate: 1.0
  min_fit_clients: 5
  min_evaluate_clients: 5
  min_available_clients: 5
`

const LocalAggregatorConfig_Yaml = `
server:
  global_address: "%[1]s"
  local_address: "0.0.0.0:8080"
  local_rounds: %[2]s
  global_rounds: 40

strategy:
  fraction_fit: 1.0
  fraction_evaluate: 1.0
  min_fit_clients: 2
  min_evaluate_clients: 2
  min_available_clients: 2
`

const ClientConfig_Yaml = `
server:
  address: "%[1]s"

node_config:
  partition-id: %[2]s 
  num-partitions: %[3]s 

run_config:
  local-epochs: %[4]s 
  batch-size: %[5]s 
  learning-rate: %[6]s  
`

const GlobalAggregatorServingConfig_Yaml = `
server:
  address: "0.0.0.0:8000"
model:
  name: "model_resnet18.pt"
`

const LocalAggregatorServingConfig_Yaml = `
server:
  address: "0.0.0.0:8000"
model:
  name: "model_resnet18.pt"
`

const ClientServingConfig_Yaml = `
server:
  address: "0.0.0.0:8000"
model:
  name: "model_resnet18.pt"
`
