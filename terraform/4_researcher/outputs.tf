output "ecr_repository_url" {
  description = "URL del repositorio ECR"
  value       = aws_ecr_repository.researcher.repository_url
}

output "service_url" {
  description = "URL pública del servicio (ALB)"
  value       = "http://${aws_lb.researcher.dns_name}"
}

output "ecs_cluster_name" {
  description = "Nombre del cluster ECS"
  value       = aws_ecs_cluster.researcher.name
}

output "ecs_service_name" {
  description = "Nombre del servicio ECS"
  value       = aws_ecs_service.researcher.name
}

output "scheduler_status" {
  description = "Estado del programador automático"
  value       = var.scheduler_enabled ? "Activado - Ejecutándose cada 2 horas" : "Desactivado"
}

output "setup_instructions" {
  description = "Instrucciones para completar la configuración"
  value       = <<-EOT
    
    ✅ ¡Servicio Researcher desplegado con éxito (ECS + ALB)!
    
    URL del servicio: http://${aws_lb.researcher.dns_name}
    
    Prueba el researcher:
    curl http://${aws_lb.researcher.dns_name}/health
    
    ${var.scheduler_enabled ? "⏰ La investigación automática se ejecuta cada 2 horas" : "💡 Para activar la investigación automática, pon scheduler_enabled = true"}
    
    Nota: Debes construir y subir tu imagen Docker a ECR (tag :latest) para que ECS la ejecute.
    Sigue la guía para instrucciones sobre cómo construir y desplegar la imagen Docker.
  EOT
}