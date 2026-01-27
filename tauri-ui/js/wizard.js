/**
 * Setup Wizard Component
 * Zero-to-Hero setup wizard for MMORPG AI Training School
 */

class SetupWizard {
  constructor() {
    this.currentStep = 0;
    this.steps = [
      'hardware',
      'game',
      'task',
      'model',
      'data',
      'review'
    ];

    this.state = {
      hardware: null,
      game: null,
      gameName: null,
      task: null,
      taskInfo: null,
      model: null,
      modelRecommendation: null,
      config: {}
    };

    this.onComplete = null;
  }

  async start() {
    this.currentStep = 0;
    await this.detectHardware();
    this.render();
  }

  async detectHardware() {
    try {
      if (window.__TAURI__?.invoke) {
        // Try to get hardware info from backend
        const info = await window.__TAURI__.invoke('config_get_hardware');
        this.state.hardware = info;
      } else {
        // Fallback detection
        this.state.hardware = {
          tier: 'medium',
          gpu_name: 'Unknown GPU',
          gpu_vram_mb: 8192,
          cpu_cores: navigator.hardwareConcurrency || 4,
          ram_mb: 8192,
          cuda_available: false,
          summary: 'Hardware detection limited in browser mode'
        };
      }
    } catch (e) {
      console.warn('Hardware detection failed:', e);
      this.state.hardware = {
        tier: 'medium',
        gpu_name: 'Detection failed',
        summary: 'Using default medium tier settings'
      };
    }
  }

  render() {
    const step = this.steps[this.currentStep];
    const container = document.getElementById('wizard-content');
    if (!container) return;

    switch (step) {
      case 'hardware':
        this.renderHardwareStep(container);
        break;
      case 'game':
        this.renderGameStep(container);
        break;
      case 'task':
        this.renderTaskStep(container);
        break;
      case 'model':
        this.renderModelStep(container);
        break;
      case 'data':
        this.renderDataStep(container);
        break;
      case 'review':
        this.renderReviewStep(container);
        break;
    }

    this.updateProgress();
  }

  updateProgress() {
    const progressSteps = document.querySelectorAll('.wizard-progress-step');
    progressSteps.forEach((el, i) => {
      el.classList.remove('completed', 'active');
      if (i < this.currentStep) {
        el.classList.add('completed');
      } else if (i === this.currentStep) {
        el.classList.add('active');
      }
    });

    const indicator = document.getElementById('wizard-step-indicator');
    if (indicator) {
      indicator.textContent = `Step ${this.currentStep + 1} of ${this.steps.length}`;
    }
  }

  renderHardwareStep(container) {
    const hw = this.state.hardware;
    const tierColors = {
      low: '#FF5252',
      medium: '#FFB74D',
      high: '#69F0AE'
    };

    container.innerHTML = `
      <div class="wizard-step-content">
        <h2 style="margin-bottom: 10px;">Hardware Detected</h2>
        <p style="color: var(--text-dim); margin-bottom: 25px;">
          We've analyzed your system to recommend optimal settings.
        </p>

        <div class="recommendation-card" style="border-color: ${tierColors[hw.tier] || '#FFB74D'}">
          <div class="recommendation-header">
            <div>
              <div class="recommendation-badge" style="background: ${tierColors[hw.tier] || '#FFB74D'}">
                ${(hw.tier || 'MEDIUM').toUpperCase()} TIER
              </div>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 20px;">
            <div class="metric-card">
              <div class="metric-label">GPU</div>
              <div class="metric-value" style="font-size: 16px;">${hw.gpu_name || 'Not detected'}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">VRAM</div>
              <div class="metric-value">${hw.gpu_vram_mb ? Math.round(hw.gpu_vram_mb / 1024) + 'GB' : 'N/A'}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">CPU Cores</div>
              <div class="metric-value">${hw.cpu_cores || 'N/A'}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">CUDA</div>
              <div class="metric-value" style="color: ${hw.cuda_available ? 'var(--success)' : 'var(--accent)'}">
                ${hw.cuda_available ? 'Available' : 'Not Available'}
              </div>
            </div>
          </div>

          <p style="color: var(--text-dim); margin-top: 15px; font-size: 13px;">
            ${this.getHardwareDescription(hw.tier)}
          </p>
        </div>
      </div>
    `;
  }

  getHardwareDescription(tier) {
    const descriptions = {
      low: 'Your hardware is suitable for lightweight models like MobileNetV3. Training may be slower, but inference will be efficient.',
      medium: 'Good hardware for most tasks. EfficientNet models will work well with moderate temporal features.',
      high: 'Excellent hardware! You can use the full EfficientNet-LSTM with maximum temporal frames for best accuracy.'
    };
    return descriptions[tier] || descriptions.medium;
  }

  async renderGameStep(container) {
    // Get available games
    let games = [
      { id: 'world_of_warcraft', name: 'World of Warcraft', icon: '⚔️' },
      { id: 'guild_wars_2', name: 'Guild Wars 2', icon: '🛡️' },
      { id: 'final_fantasy_xiv', name: 'Final Fantasy XIV', icon: '✨' },
      { id: 'lost_ark', name: 'Lost Ark', icon: '💎' },
      { id: 'new_world', name: 'New World', icon: '🌎' }
    ];

    container.innerHTML = `
      <div class="wizard-step-content">
        <h2 style="margin-bottom: 10px;">Select Your Game</h2>
        <p style="color: var(--text-dim); margin-bottom: 25px;">
          Choose the game you want to train your AI for.
        </p>

        <div class="game-grid">
          ${games.map(game => `
            <div class="game-card ${this.state.game === game.id ? 'selected' : ''}"
                 data-game-id="${game.id}">
              <div class="game-card-icon">${game.icon}</div>
              <div class="game-card-name">${game.name}</div>
              <div class="game-card-status">SUPPORTED</div>
            </div>
          `).join('')}

          <div class="game-card" data-game-id="custom" style="border-style: dashed;">
            <div class="game-card-icon">➕</div>
            <div class="game-card-name">Custom Game</div>
            <div class="game-card-status">CREATE NEW</div>
          </div>
        </div>
      </div>
    `;

    // Add click handlers
    container.querySelectorAll('.game-card').forEach(card => {
      card.addEventListener('click', () => {
        container.querySelectorAll('.game-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        this.state.game = card.dataset.gameId;
        this.state.gameName = card.querySelector('.game-card-name').textContent;
      });
    });
  }

  renderTaskStep(container) {
    const tasks = [
      { id: 'combat', name: 'Combat', icon: '⚔️', temporal: true, description: 'Real-time combat with reaction requirements' },
      { id: 'farming', name: 'Farming', icon: '🌾', temporal: false, description: 'Resource gathering and repetitive tasks' },
      { id: 'navigation', name: 'Navigation', icon: '🗺️', temporal: true, description: 'Pathfinding and movement' },
      { id: 'crafting', name: 'Crafting', icon: '🔨', temporal: false, description: 'Crafting UI interaction' }
    ];

    container.innerHTML = `
      <div class="wizard-step-content">
        <h2 style="margin-bottom: 10px;">Select Your Task</h2>
        <p style="color: var(--text-dim); margin-bottom: 25px;">
          What do you want your AI to learn for ${this.state.gameName || 'your game'}?
        </p>

        <div class="game-grid" style="grid-template-columns: repeat(2, 1fr);">
          ${tasks.map(task => `
            <div class="game-card ${this.state.task === task.id ? 'selected' : ''}"
                 data-task-id="${task.id}" style="text-align: left; padding: 25px;">
              <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
                <div style="font-size: 32px;">${task.icon}</div>
                <div>
                  <div class="game-card-name">${task.name}</div>
                  ${task.temporal ? '<span style="font-size: 10px; color: var(--primary);">TEMPORAL</span>' : ''}
                </div>
              </div>
              <p style="color: var(--text-dim); font-size: 13px;">${task.description}</p>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    container.querySelectorAll('.game-card').forEach(card => {
      card.addEventListener('click', () => {
        container.querySelectorAll('.game-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        this.state.task = card.dataset.taskId;
        this.state.taskInfo = tasks.find(t => t.id === card.dataset.taskId);
      });
    });
  }

  renderModelStep(container) {
    const hw = this.state.hardware;
    const task = this.state.taskInfo;

    // Recommend model based on hardware and task
    let recommendation;
    if (hw.tier === 'high' && task?.temporal) {
      recommendation = {
        architecture: 'efficientnet_lstm',
        name: 'EfficientNet-LSTM',
        confidence: 0.95,
        reasons: [
          'Optimal for high-end hardware',
          'Supports temporal processing for reactions',
          `Perfect for ${task.name} tasks`
        ],
        speed: 'medium',
        accuracy: 'best',
        vram: 2500
      };
    } else if (hw.tier === 'low') {
      recommendation = {
        architecture: 'mobilenetv3',
        name: 'MobileNetV3',
        confidence: 0.88,
        reasons: [
          'Optimized for limited hardware',
          'Fast inference time',
          'Good enough accuracy for most tasks'
        ],
        speed: 'fast',
        accuracy: 'good',
        vram: 800
      };
    } else {
      recommendation = {
        architecture: 'efficientnet_simple',
        name: 'EfficientNet (Balanced)',
        confidence: 0.90,
        reasons: [
          'Good balance of speed and accuracy',
          'Works well on medium hardware',
          'Suitable for most task types'
        ],
        speed: 'medium',
        accuracy: 'better',
        vram: 1500
      };
    }

    this.state.modelRecommendation = recommendation;

    container.innerHTML = `
      <div class="wizard-step-content">
        <h2 style="margin-bottom: 10px;">Model Recommendation</h2>
        <p style="color: var(--text-dim); margin-bottom: 25px;">
          Based on your hardware and task, we recommend:
        </p>

        <div class="recommendation-card">
          <div class="recommendation-header">
            <div>
              <div class="recommendation-badge">RECOMMENDED</div>
              <div class="recommendation-title" style="margin-top: 10px;">${recommendation.name}</div>
            </div>
            <div class="recommendation-confidence">${Math.round(recommendation.confidence * 100)}%</div>
          </div>

          <ul class="recommendation-reasons">
            ${recommendation.reasons.map(r => `<li>${r}</li>`).join('')}
          </ul>

          <div style="display: flex; gap: 20px; margin-top: 20px;">
            <div>
              <span style="color: var(--text-dim); font-size: 12px;">Speed</span>
              <div style="font-weight: 700; text-transform: uppercase;">${recommendation.speed}</div>
            </div>
            <div>
              <span style="color: var(--text-dim); font-size: 12px;">Accuracy</span>
              <div style="font-weight: 700; text-transform: uppercase;">${recommendation.accuracy}</div>
            </div>
            <div>
              <span style="color: var(--text-dim); font-size: 12px;">Est. VRAM</span>
              <div style="font-weight: 700;">${recommendation.vram}MB</div>
            </div>
          </div>
        </div>

        <div style="margin-top: 20px;">
          <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
            <input type="checkbox" id="use-recommended" checked style="width: 18px; height: 18px;">
            <span>Use recommended model</span>
          </label>
        </div>
      </div>
    `;

    this.state.model = recommendation.architecture;
  }

  renderDataStep(container) {
    const minSamples = 5000;
    const tips = [
      'Play naturally - the bot learns from your playstyle',
      'Include variety - different situations help generalization',
      'Maintain consistent key bindings during recording'
    ];

    if (this.state.taskInfo?.temporal) {
      tips.push('Record continuous gameplay sessions (not short clips)');
      tips.push('Include combat sequences with enemy reactions');
    }

    container.innerHTML = `
      <div class="wizard-step-content">
        <h2 style="margin-bottom: 10px;">Data Collection Tips</h2>
        <p style="color: var(--text-dim); margin-bottom: 25px;">
          Quality training data is key to a good model.
        </p>

        <div class="recommendation-card" style="border-color: var(--secondary);">
          <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 15px;">
            <div style="font-size: 48px;">📊</div>
            <div>
              <div style="font-size: 14px; color: var(--text-dim);">Minimum Samples</div>
              <div style="font-size: 32px; font-weight: 700; color: var(--secondary);">${minSamples.toLocaleString()}</div>
            </div>
          </div>

          <h4 style="margin-bottom: 10px;">Tips for Quality Data:</h4>
          <ul style="list-style: none; padding: 0;">
            ${tips.map(tip => `
              <li style="display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; color: var(--text-dim);">
                <span style="color: var(--success);">✓</span>
                <span>${tip}</span>
              </li>
            `).join('')}
          </ul>
        </div>

        <div class="stats-bar" style="margin-top: 20px;">
          <div class="stat-item">
            <div class="stat-label">Recording Hotkey</div>
            <div class="stat-val">F9</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">Stop Hotkey</div>
            <div class="stat-val">F10</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">Format</div>
            <div class="stat-val">PNG + JSON</div>
          </div>
        </div>
      </div>
    `;
  }

  renderReviewStep(container) {
    const hw = this.state.hardware;
    const rec = this.state.modelRecommendation;

    container.innerHTML = `
      <div class="wizard-step-content">
        <h2 style="margin-bottom: 10px;">Review Configuration</h2>
        <p style="color: var(--text-dim); margin-bottom: 25px;">
          Confirm your settings before starting.
        </p>

        <div class="card" style="cursor: default; margin-bottom: 15px;">
          <h3 style="margin-bottom: 15px;">Summary</h3>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div>
              <div style="color: var(--text-dim); font-size: 12px;">Game</div>
              <div style="font-weight: 700;">${this.state.gameName || 'Not selected'}</div>
            </div>
            <div>
              <div style="color: var(--text-dim); font-size: 12px;">Task</div>
              <div style="font-weight: 700;">${this.state.taskInfo?.name || 'Not selected'}</div>
            </div>
            <div>
              <div style="color: var(--text-dim); font-size: 12px;">Model</div>
              <div style="font-weight: 700;">${rec?.name || 'Not selected'}</div>
            </div>
            <div>
              <div style="color: var(--text-dim); font-size: 12px;">Hardware Tier</div>
              <div style="font-weight: 700; text-transform: uppercase;">${hw?.tier || 'medium'}</div>
            </div>
          </div>
        </div>

        <div class="card" style="cursor: default; background: rgba(3, 218, 198, 0.1); border-color: var(--secondary);">
          <h3 style="margin-bottom: 10px; color: var(--secondary);">Next Steps</h3>
          <ol style="margin-left: 20px; color: var(--text-dim); line-height: 1.8;">
            <li>Click "Finish Setup" to save your configuration</li>
            <li>Go to "Teach (Record)" to collect training data</li>
            <li>Play the game naturally while recording</li>
            <li>Collect at least 5,000 samples</li>
            <li>Return to "Train Brain" to start training</li>
          </ol>
        </div>
      </div>
    `;
  }

  async next() {
    // Validate current step
    if (!this.validateCurrentStep()) return;

    if (this.currentStep < this.steps.length - 1) {
      this.currentStep++;
      this.render();
    } else {
      await this.finish();
    }
  }

  back() {
    if (this.currentStep > 0) {
      this.currentStep--;
      this.render();
    }
  }

  validateCurrentStep() {
    const step = this.steps[this.currentStep];

    switch (step) {
      case 'game':
        if (!this.state.game) {
          alert('Please select a game');
          return false;
        }
        break;
      case 'task':
        if (!this.state.task) {
          alert('Please select a task');
          return false;
        }
        break;
    }

    return true;
  }

  async finish() {
    // Save configuration
    this.state.config = {
      game_id: this.state.game,
      task: this.state.task,
      architecture: this.state.model,
      hardware_tier: this.state.hardware?.tier || 'medium'
    };

    try {
      if (window.__TAURI__?.invoke) {
        await window.__TAURI__.invoke('config_save_session', { config: this.state.config });
      }
    } catch (e) {
      console.warn('Failed to save config:', e);
    }

    if (this.onComplete) {
      this.onComplete(this.state.config);
    }

    // Show completion message
    alert('Setup complete! You can now start collecting training data.');
  }
}

// Export for use in main.js
window.SetupWizard = SetupWizard;
