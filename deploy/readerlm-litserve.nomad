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

    # Require GPU compute capability 7.0+ (Volta/Turing) for CUDA 12.8
    constraint {
      attribute = "${meta.gpu_compute_capability}"
      operator  = ">="
      value     = "7.0"
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
        # VRAM optimization: 4-bit quantization reduces VRAM from ~14-16GB to ~4-5GB
        QUANTIZATION_MODE      = "4bit"
        QUANTIZATION_TYPE      = "nf4"
        USE_DOUBLE_QUANT       = "true"
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
