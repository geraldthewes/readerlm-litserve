job "readerlm-litserve" {
  datacenters = ["cluster"]
  type        = "service"

  group "readerlm-litserve" {
    count = 1

    constraint {
      attribute = "${attr.cpu.arch}"
      value     = "amd64"
    }

    network {
      port "http" {
        to = 8000
      }
    }

    task "readerlm-litserve" {
      driver = "docker"

      config {
        image      = "registry.cluster:5000/readerlm-litserve:latest"
        force_pull = true
        ports      = ["http"]
      }

      resources {
        cpu    = 1000
        memory = 4096
      }

      service {
        name = "readerlm-litserve"
        port = "http"
        tags = ["urlprefix-/readerlm strip=/readerlm"]

        check {
          type     = "http"
          path     = "/health"
          interval = "30s"
          timeout  = "10s"
        }
      }
    }
  }
}
