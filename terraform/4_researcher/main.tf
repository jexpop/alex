terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Usando backend local - el estado se almacenará en terraform.tfstate en este directorio
  # Esto está agregado automáticamente al .gitignore por seguridad
}

provider "aws" {
  region = var.aws_region
}

# Fuente de datos para la identidad actual del llamador
data "aws_caller_identity" "current" {}

# ========================================
# Red (usando Default VPC para simplicidad educativa)
# ========================================

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ========================================
# Repositorio ECR
# ========================================

# Repositorio ECR para la imagen Docker de researcher
resource "aws_ecr_repository" "researcher" {
  name                 = "alex-researcher"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # Permite borrar incluso si hay imágenes

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# ========================================
# ECS Fargate + ALB (equivalente "tipo App Runner")
# ========================================

# CloudWatch logs para el contenedor
resource "aws_cloudwatch_log_group" "researcher" {
  name              = "/ecs/alex-researcher"
  retention_in_days = 14

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# ECS cluster
resource "aws_ecs_cluster" "researcher" {
  name = "alex-researcher"

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# Seguridad: ALB público -> tasks (8000)
resource "aws_security_group" "alb" {
  name        = "alex-researcher-alb-sg"
  description = "ALB public access"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

resource "aws_security_group" "tasks" {
  name        = "alex-researcher-tasks-sg"
  description = "Allow ALB to reach ECS tasks"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "From ALB to container port"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# ALB + Target Group + Listener
resource "aws_lb" "researcher" {
  name               = "alex-researcher-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

resource "aws_lb_target_group" "researcher" {
  name        = "alex-researcher-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    path                = "/health"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.researcher.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.researcher.arn
  }
}

# IAM roles para tasks ECS
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "alex-researcher-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "alex-researcher-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

resource "aws_iam_role_policy" "ecs_task_bedrock_access" {
  name = "alex-researcher-ecs-task-bedrock-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels"
        ]
        Resource = "*"
      }
    ]
  })
}

# Task definition + service
resource "aws_ecs_task_definition" "researcher" {
  family                   = "alex-researcher"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "alex-researcher"
      image     = "${aws_ecr_repository.researcher.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "OPENAI_API_KEY", value = var.openai_api_key },
        { name = "BEDROCK_MODEL", value = "bedrock/us.amazon.nova-pro-v1:0" },
        { name = "ALEX_API_ENDPOINT", value = var.alex_api_endpoint },
        { name = "ALEX_API_KEY", value = var.alex_api_key }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.researcher.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

resource "aws_ecs_service" "researcher" {
  name            = "alex-researcher"
  cluster         = aws_ecs_cluster.researcher.id
  task_definition = aws_ecs_task_definition.researcher.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.researcher.arn
    container_name   = "alex-researcher"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# ========================================
# Programador EventBridge (Opcional)
# ========================================

# Rol IAM para EventBridge
resource "aws_iam_role" "eventbridge_role" {
  count = var.scheduler_enabled ? 1 : 0
  name  = "alex-eventbridge-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# Función Lambda para invocar researcher
resource "aws_lambda_function" "scheduler_lambda" {
  count         = var.scheduler_enabled ? 1 : 0
  function_name = "alex-researcher-scheduler"
  role          = aws_iam_role.lambda_scheduler_role[0].arn

  # Nota: El paquete de despliegue se creará siguiendo las instrucciones de la guía
  filename         = "${path.module}/../../backend/scheduler/lambda_function.zip"
  source_code_hash = fileexists("${path.module}/../../backend/scheduler/lambda_function.zip") ? filebase64sha256("${path.module}/../../backend/scheduler/lambda_function.zip") : null

  handler     = "lambda_function.handler"
  runtime     = "python3.13"
  timeout     = 180 # 3 minutos para manejar el tiempo de respuesta de App Runner
  memory_size = 256

  environment {
    variables = {
      APP_URL = "http://${aws_lb.researcher.dns_name}"
    }
  }

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# Rol IAM para la Lambda del programador
resource "aws_iam_role" "lambda_scheduler_role" {
  count = var.scheduler_enabled ? 1 : 0
  name  = "alex-scheduler-lambda-role"

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

  tags = {
    Project = "alex"
    Part    = "4"
  }
}

# Política básica de ejecución para Lambda
resource "aws_iam_role_policy_attachment" "lambda_scheduler_basic" {
  count      = var.scheduler_enabled ? 1 : 0
  role       = aws_iam_role.lambda_scheduler_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Programación en EventBridge
resource "aws_scheduler_schedule" "research_schedule" {
  count = var.scheduler_enabled ? 1 : 0
  name  = "alex-research-schedule"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "rate(2 hours)"

  target {
    arn      = aws_lambda_function.scheduler_lambda[0].arn
    role_arn = aws_iam_role.eventbridge_role[0].arn
  }
}

# Permiso para que EventBridge invoque Lambda
resource "aws_lambda_permission" "allow_eventbridge" {
  count         = var.scheduler_enabled ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler_lambda[0].function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.research_schedule[0].arn
}

# Política para que EventBridge invoque Lambda
resource "aws_iam_role_policy" "eventbridge_invoke_lambda" {
  count = var.scheduler_enabled ? 1 : 0
  name  = "InvokeLambdaPolicy"
  role  = aws_iam_role.eventbridge_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = aws_lambda_function.scheduler_lambda[0].arn
      }
    ]
  })
}