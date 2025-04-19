aws cloudformation create-stack \
  --stack-name game-infrastructure \
  --template-body file://game-template.yaml \
  --parameters file://parameters.json \
  --capabilities CAPABILITY_IAM
