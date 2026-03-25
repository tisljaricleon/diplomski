curl -X POST http://10.19.4.45:8080/fl/start \
  -H "Content-Type: application/json" \
  -d '{
    "epochs": 10,
    "localRounds": 5,
    "trainingParams": {
      "batchSize": 32,
      "learningRate": 0.01
    },
    "modelSize": 10.0,
    "costSource": "communication",
    "costConfiguration": {
      "costType": "totalBudget",
      "budget": 400000
    },
    "configurationModel": "minKld",
    "rvaEnabled": false,
    "enableServing": true
  }'