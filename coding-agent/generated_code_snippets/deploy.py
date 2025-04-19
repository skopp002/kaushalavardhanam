
import boto3
import json

# AWS Clients
dynamodb = boto3.resource('dynamodb')
gamelift = boto3.client('gamelift')
cognito = boto3.client('cognito-idp')
api_gateway = boto3.client('apigateway')

# DynamoDB Table
table = dynamodb.Table('GameData')

# Cognito User Pool
user_pool_id = 'YOUR_USER_POOL_ID'
app_client_id = 'YOUR_APP_CLIENT_ID'

# API Gateway
rest_api_id = 'YOUR_REST_API_ID'
resource_id = 'YOUR_RESOURCE_ID'
http_method = 'POST'

# GameLift Configuration
build_id = 'YOUR_BUILD_ID'
fleet_id = 'YOUR_FLEET_ID'
alias_id = 'YOUR_ALIAS_ID'

# Helper Functions
def get_user(username):
    try:
        response = cognito.admin_get_user(
            UserPoolId=user_pool_id,
            Username=username
        )
        return response['UserAttributes']
    except cognito.exceptions.UserNotFoundException:
        return None

def create_game_session(user_data):
    try:
        response = gamelift.create_game_session(
            MaxPlayers=2,
            AliasId=alias_id,
            FleetId=fleet_id,
            GameProperties=[
                {
                    'Key': 'userId',
                    'Value': user_data['sub']
                },
                {
                    'Key': 'username',
                    'Value': user_data['username']
                }
            ]
        )
        return response['GameSession']
    except Exception as e:
        print(e)
        return None

def save_game_data(game_session, user_data):
    table.put_item(
        Item={
            'gameSessionId': game_session['GameSessionId'],
            'userId': user_data['sub'],
            'username': user_data['username'],
            'gameSessionData': game_session['GameSessionData']
        }
    )

# API Gateway Lambda Function
def lambda_handler(event, context):
    # Get user data from Cognito
    username = event['requestContext']['authorizer']['claims']['username']
    user_data = get_user(username)

    if user_data:
        # Create a new game session
        game_session = create_game_session(user_data)

        if game_session:
            # Save game data to DynamoDB
            save_game_data(game_session, user_data)

            # Return game session data
            return {
                'statusCode': 200,
                'body': json.dumps(game_session)
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to create game session'})
            }
    else:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthorized'})
        }

# Deploy Lambda Function
lambda_client = boto3.client('lambda')
lambda_function_name = 'YOUR_LAMBDA_FUNCTION_NAME'
lambda_role_arn = 'YOUR_LAMBDA_ROLE_ARN'

try:
    lambda_client.create_function(
        FunctionName=lambda_function_name,
        Runtime='python3.9',
        Role=lambda_role_arn,
        Handler='lambda_function.lambda_handler',
        Code={
            'ZipFile': open('lambda_function.py', 'rb').read()
        }
    )
except lambda_client.exceptions.ResourceConflictException:
    lambda_client.update_function_code(
        FunctionName=lambda_function_name,
        ZipFile=open('lambda_function.py', 'rb').read()
    )

# Create API Gateway Integration
api_gateway.put_integration(
    RestApiId=rest_api_id,
    ResourceId=resource_id,
    HttpMethod=http_method,
    Type='AWS_PROXY',
    IntegrationHttpMethod='POST',
    Uri='arn:aws:apigateway:YOUR_REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:YOUR_REGION:YOUR_ACCOUNT_ID:function:' + lambda_function_name + '/invocations'
)

# Deploy API Gateway
api_gateway.create_deployment(
    RestApiId=rest_api_id,
    StageName='prod'
)

"""
This code demonstrates how to use AWS services like GameLift, DynamoDB, API Gateway, and Cognito to create a game session and store game data. Here's a breakdown of the code:

1. **Imports**: The necessary AWS SDK libraries are imported.
2. **AWS Clients**: Clients for DynamoDB, GameLift, Cognito, and API Gateway are created.
3. **DynamoDB Table**: A DynamoDB table named 'GameData' is defined.
4. **Cognito User Pool**: The Cognito user pool ID and app client ID are defined.
5. **API Gateway**: The API Gateway REST API ID, resource ID, and HTTP method are defined.
6. **GameLift Configuration**: The GameLift build ID, fleet ID, and alias ID are defined.
7. **Helper Functions**:
   - `get_user`: Retrieves user data from Cognito based on the username.
   - `create_game_session`: Creates a new game session in GameLift with the user's ID and username as game properties.
   - `save_game_data`: Saves the game session data to the DynamoDB table.
8. **API Gateway Lambda Function**: The `lambda_handler` function is the entry point for the API Gateway Lambda function. It handles the following tasks:
   - Retrieves the user data from Cognito based on the username in the request context.
   - Creates a new game session in GameLift with the user's data.
   - Saves the game session data to the DynamoDB table.
   - Returns the game session data as the response.
9. **Deploy Lambda Function**: The code creates or updates a Lambda function with the provided name and role ARN, using the `lambda_function.py` file as the code source.
10. **Create API Gateway Integration**: The code creates an API Gateway integration between the specified resource and the deployed Lambda function.
11. **Deploy API Gateway**: The code deploys the API Gateway changes to the 'prod' stage.

Note: You need to replace the placeholders (`YOUR_USER_POOL_ID`, `YOUR_APP_CLIENT_ID`, `YOUR_REST_API_ID`, `YOUR_RESOURCE_ID`, `YOUR_BUILD_ID`, `YOUR_FLEET_ID`, `YOUR_ALIAS_ID`, `YOUR_LAMBDA_FUNCTION_NAME`, `YOUR_LAMBDA_ROLE_ARN`, `YOUR_REGION`, and `YOUR_ACCOUNT_ID`) with your actual AWS resource IDs and values.
"""