job "readerlm-litserve" {
  datacenters = ["cluster"]
  type        = "service"

  group "readerlm-litserve" {
    count = 1

    # Exclude dedicated GPU nodes (reserved for ollama, nemotron, llama-swap)
    constraint {
      attribute = "${meta.gpu-dedicated}"
      operator  = "!="
      value     = "true"
    }

    constraint {
      attribute = "${attr.cpu.arch}"
      value     = "amd64"
    }

    # Only schedule on nodes with dedicated HuggingFace cache storage
    constraint {
      attribute = "${meta.hf-cache-storage}"
      value     = "true"
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
        privileged = true
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
