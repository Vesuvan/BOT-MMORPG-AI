# Integrating ModelHub into your existing launcher (optional)

This patch ships ModelHub as a separate Eel app:
  python launcher_modelhub/launcher.py

If you want a button inside your existing Eel launcher to open ModelHub,
you can add a button in your current launcher UI that runs:

  python launcher_modelhub/launcher.py

Keep it separate so you don't risk breaking existing launcher code.
