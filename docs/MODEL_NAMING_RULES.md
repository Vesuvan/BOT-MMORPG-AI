# ModelHub Naming Rules (Local-Only Default)

## Game ID
- lowercase snake_case: a-z, 0-9, _
- examples: genshin_impact, world_of_warcraft, new_world

## Model ID
- lowercase snake_case
- include intent + arch + version suffix
- recommended pattern:
  <type>_<arch>_v<number>
- examples:
  combat_resnet50_v2
  farming_mobilenetv2_v1
  navigation_unet_v3

## Local folder layout
trained_models/<game_id>/<model_id>/

Required:
- metadata.json (or legacy profile.json)
- model.pth OR model_best.pth (PyTorch checkpoint)

Legacy formats (still supported):
- model.keras OR model.h5 (TensorFlow/Keras)

Optional:
- metrics.json
- README.md
