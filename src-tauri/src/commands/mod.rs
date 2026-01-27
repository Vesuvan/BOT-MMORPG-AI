// Training School Commands Module
// Additional commands for the AI Training School features

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Debug, Serialize, Deserialize)]
pub struct HardwareInfo {
    pub platform: String,
    pub cpu_cores: u32,
    pub ram_mb: u64,
    pub gpu_name: Option<String>,
    pub gpu_vram_mb: Option<u64>,
    pub cuda_available: bool,
    pub tier: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GameProfile {
    pub id: String,
    pub name: String,
    pub status: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ModelRecommendation {
    pub architecture: String,
    pub architecture_name: String,
    pub confidence: f64,
    pub reasons: Vec<String>,
    pub warnings: Vec<String>,
    pub estimated_speed: String,
    pub estimated_accuracy: String,
    pub recommended_input_size: Vec<u32>,
    pub recommended_batch_size: u32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TrainingMetrics {
    pub epoch: u32,
    pub total_epochs: u32,
    pub phase: String,
    pub train_loss: f64,
    pub train_accuracy: f64,
    pub val_loss: f64,
    pub val_accuracy: f64,
    pub learning_rate: f64,
    pub eta_seconds: u32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct InferenceStats {
    pub fps: f64,
    pub latency_ms: f64,
    pub confidence: f64,
    pub action: String,
    pub actions_count: u64,
}

// These commands will be registered in main.rs
// They communicate with the Python bridge via JSON-RPC

pub mod training_school {
    use super::*;

    /// Get hardware information for model recommendations
    pub fn get_hardware_info() -> HardwareInfo {
        // This would normally call the Python bridge
        // For now, return detected info from system

        let cpu_cores = num_cpus::get() as u32;

        // Try to get GPU info (simplified)
        let (gpu_name, gpu_vram, cuda) = detect_gpu();

        let tier = if cuda && gpu_vram.unwrap_or(0) >= 8192 {
            "high"
        } else if cuda && gpu_vram.unwrap_or(0) >= 4096 {
            "medium"
        } else {
            "low"
        };

        HardwareInfo {
            platform: std::env::consts::OS.to_string(),
            cpu_cores,
            ram_mb: get_system_memory(),
            gpu_name,
            gpu_vram_mb: gpu_vram,
            cuda_available: cuda,
            tier: tier.to_string(),
        }
    }

    fn detect_gpu() -> (Option<String>, Option<u64>, bool) {
        // Simplified GPU detection
        // In production, this would use nvml or similar
        #[cfg(target_os = "windows")]
        {
            // Check for NVIDIA GPU via environment or registry
            if std::env::var("CUDA_PATH").is_ok() {
                return (Some("NVIDIA GPU (CUDA available)".to_string()), Some(8192), true);
            }
        }

        #[cfg(target_os = "linux")]
        {
            // Check for nvidia-smi
            if std::path::Path::new("/usr/bin/nvidia-smi").exists() {
                return (Some("NVIDIA GPU".to_string()), Some(8192), true);
            }
        }

        (None, None, false)
    }

    fn get_system_memory() -> u64 {
        // Simplified memory detection
        // Returns MB
        #[cfg(target_os = "linux")]
        {
            if let Ok(content) = std::fs::read_to_string("/proc/meminfo") {
                for line in content.lines() {
                    if line.starts_with("MemTotal:") {
                        if let Some(kb_str) = line.split_whitespace().nth(1) {
                            if let Ok(kb) = kb_str.parse::<u64>() {
                                return kb / 1024;
                            }
                        }
                    }
                }
            }
        }

        // Default 8GB
        8192
    }

    /// List available game profiles
    pub fn list_games() -> Vec<GameProfile> {
        vec![
            GameProfile {
                id: "world_of_warcraft".to_string(),
                name: "World of Warcraft".to_string(),
                status: "supported".to_string(),
            },
            GameProfile {
                id: "guild_wars_2".to_string(),
                name: "Guild Wars 2".to_string(),
                status: "supported".to_string(),
            },
            GameProfile {
                id: "final_fantasy_xiv".to_string(),
                name: "Final Fantasy XIV".to_string(),
                status: "supported".to_string(),
            },
            GameProfile {
                id: "lost_ark".to_string(),
                name: "Lost Ark".to_string(),
                status: "supported".to_string(),
            },
            GameProfile {
                id: "new_world".to_string(),
                name: "New World".to_string(),
                status: "supported".to_string(),
            },
        ]
    }
}
