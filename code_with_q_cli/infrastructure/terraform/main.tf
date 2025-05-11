provider "aws" {
  region = var.aws_region
}

# DynamoDB Tables
resource "aws_dynamodb_table" "players" {
  name           = "DharmaCraft-Players"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "PlayerId"

  attribute {
    name = "PlayerId"
    type = "S"
  }

  tags = {
    Name        = "DharmaCraft-Players"
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "game_state" {
  name           = "DharmaCraft-GameState"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "WorldId"
  range_key      = "ChunkId"

  attribute {
    name = "WorldId"
    type = "S"
  }

  attribute {
    name = "ChunkId"
    type = "S"
  }

  tags = {
    Name        = "DharmaCraft-GameState"
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "player_progress" {
  name           = "DharmaCraft-PlayerProgress"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "PlayerId"

  attribute {
    name = "PlayerId"
    type = "S"
  }

  tags = {
    Name        = "DharmaCraft-PlayerProgress"
    Environment = var.environment
  }
}

# RDS for Leaderboards
resource "aws_db_instance" "leaderboard" {
  allocated_storage    = 20
  storage_type         = "gp2"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = "db.t3.micro"
  identifier           = "dharmacraft-leaderboard"
  username             = var.db_username
  password             = var.db_password
  parameter_group_name = "default.mysql8.0"
  skip_final_snapshot  = true
  publicly_accessible  = false
  multi_az             = false

  tags = {
    Name        = "DharmaCraft-Leaderboard"
    Environment = var.environment
  }
}

# S3 Buckets
resource "aws_s3_bucket" "game_assets" {
  bucket = "dharmacraft-assets-${var.environment}"

  tags = {
    Name        = "DharmaCraft Assets"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_public_access_block" "game_assets_public_access" {
  bucket = aws_s3_bucket.game_assets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "assets_distribution" {
  origin {
    domain_name = aws_s3_bucket.game_assets.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.game_assets.bucket}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.oai.cloudfront_access_identity_path
    }
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.game_assets.bucket}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  price_class = "PriceClass_100"

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name        = "DharmaCraft-Assets-CDN"
    Environment = var.environment
  }
}

resource "aws_cloudfront_origin_access_identity" "oai" {
  comment = "OAI for DharmaCraft assets"
}

# API Gateway
resource "aws_api_gateway_rest_api" "game_api" {
  name        = "dharmacraft-api"
  description = "API for DharmaCraft game"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# Lambda Functions
resource "aws_lambda_function" "auth_lambda" {
  function_name = "dharmacraft-auth"
  handler       = "auth.handler"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "nodejs18.x"
  filename      = "../backend/lambda/auth.zip"
  source_code_hash = filebase64sha256("../backend/lambda/auth.zip")
  timeout       = 10
  memory_size   = 128

  environment {
    variables = {
      PLAYERS_TABLE = aws_dynamodb_table.players.name
    }
  }
}

resource "aws_lambda_function" "matchmaking_lambda" {
  function_name = "dharmacraft-matchmaking"
  handler       = "matchmaking.handler"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "nodejs18.x"
  filename      = "../backend/lambda/matchmaking.zip"
  source_code_hash = filebase64sha256("../backend/lambda/matchmaking.zip")
  timeout       = 15
  memory_size   = 128

  environment {
    variables = {
      GAMELIFT_FLEET_ID = var.gamelift_fleet_id
    }
  }
}

resource "aws_lambda_function" "save_game_lambda" {
  function_name = "dharmacraft-save-game"
  handler       = "saveGame.handler"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "nodejs18.x"
  filename      = "../backend/lambda/saveGame.zip"
  source_code_hash = filebase64sha256("../backend/lambda/saveGame.zip")
  timeout       = 15
  memory_size   = 256

  environment {
    variables = {
      GAME_STATE_TABLE = aws_dynamodb_table.game_state.name
      PLAYER_PROGRESS_TABLE = aws_dynamodb_table.player_progress.name
    }
  }
}

resource "aws_lambda_function" "leaderboard_lambda" {
  function_name = "dharmacraft-leaderboard"
  handler       = "leaderboard.handler"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "nodejs18.x"
  filename      = "../backend/lambda/leaderboard.zip"
  source_code_hash = filebase64sha256("../backend/lambda/leaderboard.zip")
  timeout       = 10
  memory_size   = 128

  environment {
    variables = {
      DB_HOST     = aws_db_instance.leaderboard.address
      DB_PORT     = aws_db_instance.leaderboard.port
      DB_NAME     = "leaderboard"
      DB_USERNAME = var.db_username
      DB_PASSWORD = var.db_password
    }
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "dharmacraft-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "dharmacraft-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Effect   = "Allow"
        Resource = [
          aws_dynamodb_table.players.arn,
          aws_dynamodb_table.game_state.arn,
          aws_dynamodb_table.player_progress.arn
        ]
      },
      {
        Action = [
          "gamelift:CreateGameSession",
          "gamelift:DescribeGameSessions",
          "gamelift:CreatePlayerSession",
          "gamelift:DescribePlayerSessions"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# API Gateway Integration with Lambda
resource "aws_api_gateway_resource" "auth" {
  rest_api_id = aws_api_gateway_rest_api.game_api.id
  parent_id   = aws_api_gateway_rest_api.game_api.root_resource_id
  path_part   = "auth"
}

resource "aws_api_gateway_method" "auth_post" {
  rest_api_id   = aws_api_gateway_rest_api.game_api.id
  resource_id   = aws_api_gateway_resource.auth.id
  http_method   = "POST"
  authorization_type = "NONE"
}

resource "aws_api_gateway_integration" "auth_integration" {
  rest_api_id = aws_api_gateway_rest_api.game_api.id
  resource_id = aws_api_gateway_resource.auth.id
  http_method = aws_api_gateway_method.auth_post.http_method
  integration_http_method = "POST"
  type        = "AWS_PROXY"
  uri         = aws_lambda_function.auth_lambda.invoke_arn
}

# Similar resources for matchmaking, save-game, and leaderboard endpoints

# API Gateway Deployment
resource "aws_api_gateway_deployment" "api_deployment" {
  depends_on = [
    aws_api_gateway_integration.auth_integration
    # Add other integrations here
  ]

  rest_api_id = aws_api_gateway_rest_api.game_api.id
  stage_name  = var.environment
}

# Outputs
output "api_gateway_url" {
  value = "${aws_api_gateway_deployment.api_deployment.invoke_url}"
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.assets_distribution.domain_name
}

output "rds_endpoint" {
  value = aws_db_instance.leaderboard.endpoint
}

output "dynamodb_players_table" {
  value = aws_dynamodb_table.players.name
}

output "dynamodb_game_state_table" {
  value = aws_dynamodb_table.game_state.name
}

output "dynamodb_player_progress_table" {
  value = aws_dynamodb_table.player_progress.name
}

output "assets_bucket" {
  value = aws_s3_bucket.game_assets.bucket
}
