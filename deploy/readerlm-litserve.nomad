job "readerlm-litserve" {
  datacenters = ["cluster"]
  type        = "service"

  group "readerlm-litserve" {
    count = 1

    constraint {
      attribute = "${meta.gpu-capable}"
      value     = "true"
    }

    constraint {
      attribute = "${attr.cpu.arch}"
      value     = "amd64"
    }

    volume "huggingface_cache" {
      type      = "host"
      source    = "huggingface-cache"
      read_only = false
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
        runtime    = "nvidia"
        shm_size   = 2147483648
      }

      env {
        NVIDIA_VISIBLE_DEVICES = "all"
        CUDA_DEVICE_ORDER      = "PCI_BUS_ID"
      }

      volume_mount {
        volume      = "huggingface_cache"
        destination = "/home/appuser/.cache/huggingface"
      }

      resources {
        cpu    = 2000
        memory = 16384
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
