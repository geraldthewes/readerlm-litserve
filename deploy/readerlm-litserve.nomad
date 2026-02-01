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

    # Init task to fix volume permissions for appuser (UID 1000)
    task "init-permissions" {
      lifecycle {
        hook    = "prestart"
        sidecar = false
      }

      driver = "docker"

      config {
        image   = "busybox:latest"
        command = "/bin/sh"
        args    = ["-c", "mkdir -p /cache/hub && chown -R 1000:1000 /cache && chmod -R 755 /cache"]
      }

      volume_mount {
        volume      = "huggingface_cache"
        destination = "/cache"
      }

      resources {
        cpu    = 100
        memory = 64
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
