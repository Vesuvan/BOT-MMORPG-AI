"""
Tests for PyTorch Neural Network Models

Simple tests to verify that all neural network models work correctly with PyTorch.
Tests cover: model instantiation, forward pass, output shape, and parameter counting.
"""

import pytest

# Skip all tests if PyTorch not available
torch = pytest.importorskip("torch")
nn = torch.nn


class TestModelImports:
    """Test that model modules can be imported."""

    def test_models_pytorch_imports(self):
        """Test that models_pytorch module can be imported."""
        from bot_mmorpg.scripts import models_pytorch
        assert hasattr(models_pytorch, 'PYTORCH_AVAILABLE')
        assert models_pytorch.PYTORCH_AVAILABLE is True

    def test_list_models_available(self):
        """Test that list_models function is available."""
        from bot_mmorpg.scripts.models_pytorch import list_models
        models = list_models()
        # 8 original + 3 new advanced models (transformer, multihead, attention)
        assert len(models) == 11
        assert 'efficientnet_lstm' in models
        assert 'mobilenet_v3' in models
        # New advanced models
        assert 'efficientnet_transformer' in models
        assert 'multihead_action' in models
        assert 'game_attention' in models

    def test_get_model_available(self):
        """Test that get_model factory function is available."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        assert callable(get_model)


class TestModelInfo:
    """Test model metadata and info functions."""

    def test_model_info_for_all_models(self):
        """Test that MODEL_INFO exists for all registered models."""
        from bot_mmorpg.scripts.models_pytorch import list_models, get_model_info

        for model_name in list_models():
            info = get_model_info(model_name)
            assert 'name' in info
            assert 'description' in info
            assert 'params' in info
            assert 'temporal' in info

    def test_efficientnet_lstm_is_recommended(self):
        """Test that EfficientNet-LSTM is marked as recommended."""
        from bot_mmorpg.scripts.models_pytorch import get_model_info
        info = get_model_info('efficientnet_lstm')
        assert info['recommended'] is True
        assert info['temporal'] is True

    def test_mobilenet_v3_is_fast(self):
        """Test MobileNet V3 metadata."""
        from bot_mmorpg.scripts.models_pytorch import get_model_info
        info = get_model_info('mobilenet_v3')
        assert info['temporal'] is False
        assert '~2M' in info['params']


class TestModelInstantiation:
    """Test that all models can be instantiated without pretrained weights."""

    @pytest.fixture
    def num_actions(self):
        return 29

    def test_efficientnet_lstm_creates(self, num_actions):
        """Test EfficientNet-LSTM model instantiation."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('efficientnet_lstm', num_actions=num_actions, pretrained=False)
        assert isinstance(model, nn.Module)
        assert model.num_actions == num_actions

    def test_efficientnet_simple_creates(self, num_actions):
        """Test EfficientNet Simple model instantiation."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('efficientnet_simple', num_actions=num_actions, pretrained=False)
        assert isinstance(model, nn.Module)
        assert model.num_actions == num_actions

    def test_mobilenet_v3_creates(self, num_actions):
        """Test MobileNet V3 model instantiation."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('mobilenet_v3', num_actions=num_actions, pretrained=False)
        assert isinstance(model, nn.Module)
        assert model.num_actions == num_actions

    def test_resnet18_lstm_creates(self, num_actions):
        """Test ResNet18-LSTM model instantiation."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('resnet18_lstm', num_actions=num_actions, pretrained=False)
        assert isinstance(model, nn.Module)

    def test_inception_v3_creates(self, num_actions):
        """Test Inception V3 Legacy model instantiation."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('inception_v3', num_actions=num_actions)
        assert isinstance(model, nn.Module)
        assert model.num_actions == num_actions

    def test_alexnet_creates(self, num_actions):
        """Test AlexNet Legacy model instantiation."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('alexnet', num_actions=num_actions)
        assert isinstance(model, nn.Module)

    def test_sentnet_creates(self, num_actions):
        """Test SentNet 3D Legacy model instantiation."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('sentnet', num_actions=num_actions)
        assert isinstance(model, nn.Module)

    def test_sentnet_2d_creates(self, num_actions):
        """Test SentNet 2D Legacy model instantiation."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('sentnet_2d', num_actions=num_actions)
        assert isinstance(model, nn.Module)


class TestForwardPass:
    """Test forward pass for all models."""

    @pytest.fixture
    def single_frame(self):
        """Single frame input: (batch=1, C=3, H=270, W=480)."""
        return torch.randn(1, 3, 270, 480)

    @pytest.fixture
    def frame_sequence(self):
        """Frame sequence input: (batch=1, seq=4, C=3, H=270, W=480)."""
        return torch.randn(1, 4, 3, 270, 480)

    def test_efficientnet_lstm_forward_single(self, single_frame):
        """Test EfficientNet-LSTM forward pass with single frame."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('efficientnet_lstm', num_actions=29, pretrained=False)
        model.eval()
        with torch.no_grad():
            output = model(single_frame)
        assert output.shape == (1, 29)

    def test_efficientnet_lstm_forward_sequence(self, frame_sequence):
        """Test EfficientNet-LSTM forward pass with frame sequence."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('efficientnet_lstm', num_actions=29, pretrained=False)
        model.eval()
        with torch.no_grad():
            output = model(frame_sequence)
        assert output.shape == (1, 29)

    def test_efficientnet_simple_forward(self, single_frame):
        """Test EfficientNet Simple forward pass."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('efficientnet_simple', num_actions=29, pretrained=False)
        model.eval()
        with torch.no_grad():
            output = model(single_frame)
        assert output.shape == (1, 29)

    def test_mobilenet_v3_forward(self, single_frame):
        """Test MobileNet V3 forward pass."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('mobilenet_v3', num_actions=29, pretrained=False)
        model.eval()
        with torch.no_grad():
            output = model(single_frame)
        assert output.shape == (1, 29)

    def test_resnet18_lstm_forward_single(self, single_frame):
        """Test ResNet18-LSTM forward pass with single frame."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('resnet18_lstm', num_actions=29, pretrained=False)
        model.eval()
        with torch.no_grad():
            output = model(single_frame)
        assert output.shape == (1, 29)

    def test_resnet18_lstm_forward_sequence(self, frame_sequence):
        """Test ResNet18-LSTM forward pass with frame sequence."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('resnet18_lstm', num_actions=29, pretrained=False)
        model.eval()
        with torch.no_grad():
            output = model(frame_sequence)
        assert output.shape == (1, 29)

    def test_inception_v3_forward(self, single_frame):
        """Test Inception V3 forward pass."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('inception_v3', num_actions=29)
        model.eval()
        with torch.no_grad():
            output = model(single_frame)
        assert output.shape == (1, 29)

    def test_alexnet_forward(self, single_frame):
        """Test AlexNet forward pass."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('alexnet', num_actions=29)
        model.eval()
        with torch.no_grad():
            output = model(single_frame)
        assert output.shape == (1, 29)

    # Note: SentNet 3D forward test is omitted because the legacy model
    # requires very large video inputs (D>64, H>512, W>960) to pass through
    # its multiple AvgPool3d layers without dimension collapse.
    # The model instantiation is tested in TestModelInstantiation.

    def test_sentnet_2d_forward(self, single_frame):
        """Test SentNet 2D forward pass."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('sentnet_2d', num_actions=29)
        model.eval()
        with torch.no_grad():
            output = model(single_frame)
        assert output.shape == (1, 29)


class TestParameterCounting:
    """Test parameter counting for all models."""

    def test_count_parameters_function(self):
        """Test that count_parameters function works."""
        from bot_mmorpg.scripts.models_pytorch import get_model, count_parameters
        model = get_model('mobilenet_v3', num_actions=29, pretrained=False)
        params = count_parameters(model)
        assert params > 0
        assert isinstance(params, int)

    def test_mobilenet_is_smallest(self):
        """Test that MobileNet V3 has fewer parameters than EfficientNet."""
        from bot_mmorpg.scripts.models_pytorch import get_model, count_parameters

        mobilenet = get_model('mobilenet_v3', num_actions=29, pretrained=False)
        efficientnet = get_model('efficientnet_simple', num_actions=29, pretrained=False)

        mobile_params = count_parameters(mobilenet)
        efficient_params = count_parameters(efficientnet)

        assert mobile_params < efficient_params


class TestModelRegistry:
    """Test the model registry and factory."""

    def test_unknown_model_raises_error(self):
        """Test that requesting unknown model raises ValueError."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        with pytest.raises(ValueError, match="Unknown model"):
            get_model('nonexistent_model')

    def test_unknown_model_info_raises_error(self):
        """Test that get_model_info raises ValueError for unknown model."""
        from bot_mmorpg.scripts.models_pytorch import get_model_info
        with pytest.raises(ValueError, match="Unknown model"):
            get_model_info('nonexistent_model')

    def test_all_registered_models_create(self):
        """Test that all registered models can be created."""
        from bot_mmorpg.scripts.models_pytorch import list_models, get_model

        for model_name in list_models():
            model = get_model(model_name, num_actions=29, pretrained=False)
            assert isinstance(model, nn.Module)


class TestDeviceUtilities:
    """Test device utility functions."""

    def test_get_device_returns_device(self):
        """Test that get_device returns a torch.device."""
        from bot_mmorpg.scripts.models_pytorch import get_device
        device = get_device(prefer_gpu=False)
        assert isinstance(device, torch.device)
        assert device.type == 'cpu'

    def test_get_device_cpu_fallback(self):
        """Test CPU fallback when GPU not preferred."""
        from bot_mmorpg.scripts.models_pytorch import get_device
        device = get_device(prefer_gpu=False)
        assert device.type == 'cpu'


class TestLegacyCompatibility:
    """Test legacy API compatibility wrappers."""

    def test_inception_v3_legacy_wrapper(self):
        """Test inception_v3 legacy wrapper function."""
        from bot_mmorpg.scripts.models_pytorch import inception_v3
        model = inception_v3(width=480, height=270, frame_count=4, lr=0.001, output=29)
        assert isinstance(model, nn.Module)

    def test_alexnet_legacy_wrapper(self):
        """Test alexnet legacy wrapper function."""
        from bot_mmorpg.scripts.models_pytorch import alexnet
        model = alexnet(width=480, height=270, lr=0.001, output=29)
        assert isinstance(model, nn.Module)

    def test_sentnet_legacy_wrapper(self):
        """Test sentnet legacy wrapper function."""
        from bot_mmorpg.scripts.models_pytorch import sentnet
        model = sentnet(width=480, height=270, frame_count=4, lr=0.001, output=29)
        assert isinstance(model, nn.Module)

    def test_sentnet_color_2d_legacy_wrapper(self):
        """Test sentnet_color_2d legacy wrapper function."""
        from bot_mmorpg.scripts.models_pytorch import sentnet_color_2d
        model = sentnet_color_2d(width=480, height=270, frame_count=4, lr=0.001, output=29)
        assert isinstance(model, nn.Module)

    def test_googlenet_alias(self):
        """Test googlenet alias for inception_v3."""
        from bot_mmorpg.scripts.models_pytorch import googlenet
        model = googlenet(width=480, height=270, frame_count=4, lr=0.001, output=29)
        assert isinstance(model, nn.Module)


class TestModelPrediction:
    """Test model prediction methods."""

    def test_efficientnet_lstm_predict(self):
        """Test EfficientNet-LSTM predict method returns binary outputs."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('efficientnet_lstm', num_actions=29, pretrained=False)
        model.eval()

        x = torch.randn(1, 3, 270, 480)
        predictions = model.predict(x, threshold=0.5)

        assert predictions.shape == (1, 29)
        assert torch.all((predictions == 0) | (predictions == 1))


class TestBatchProcessing:
    """Test batch processing for models."""

    def test_efficientnet_lstm_batch(self):
        """Test EfficientNet-LSTM with batch of inputs."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('efficientnet_lstm', num_actions=29, pretrained=False)
        model.eval()

        # Batch of 4 frame sequences
        x = torch.randn(4, 4, 3, 270, 480)
        with torch.no_grad():
            output = model(x)
        assert output.shape == (4, 29)

    def test_mobilenet_v3_batch(self):
        """Test MobileNet V3 with batch of inputs."""
        from bot_mmorpg.scripts.models_pytorch import get_model
        model = get_model('mobilenet_v3', num_actions=29, pretrained=False)
        model.eval()

        # Batch of 4 single frames
        x = torch.randn(4, 3, 270, 480)
        with torch.no_grad():
            output = model(x)
        assert output.shape == (4, 29)
