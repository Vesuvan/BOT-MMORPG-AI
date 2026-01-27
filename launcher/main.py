#!/usr/bin/env python3
"""
BOT-MMORPG-AI Launcher

Main entry point for the AI Training School system.

Usage:
    python launcher/main.py              # Interactive mode
    python launcher/main.py --wizard     # Setup wizard only
    python launcher/main.py --quick WoW  # Quick start for known game
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from wizard import SetupWizard


def print_banner():
    """Print the welcome banner."""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ██████╗  ██████╗ ████████╗    ███╗   ███╗███╗   ███╗       ║
║   ██╔══██╗██╔═══██╗╚══██╔══╝    ████╗ ████║████╗ ████║       ║
║   ██████╔╝██║   ██║   ██║       ██╔████╔██║██╔████╔██║       ║
║   ██╔══██╗██║   ██║   ██║       ██║╚██╔╝██║██║╚██╔╝██║       ║
║   ██████╔╝╚██████╔╝   ██║       ██║ ╚═╝ ██║██║ ╚═╝ ██║       ║
║   ╚═════╝  ╚═════╝    ╚═╝       ╚═╝     ╚═╝╚═╝     ╚═╝       ║
║                                                              ║
║              AI Training School for MMORPGs                  ║
║                  Powered by PyTorch 2.x                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    )


def main_menu() -> str:
    """Display main menu and get choice."""
    print("\n" + "=" * 50)
    print("  MAIN MENU")
    print("=" * 50)
    print("\n  1. Setup Wizard (Zero-to-Hero)")
    print("  2. Collect Training Data")
    print("  3. Train Model")
    print("  4. Run Inference")
    print("  5. Settings")
    print("  6. Exit")

    choice = input("\n  Enter choice [1-6]: ").strip()
    return choice


def run_interactive():
    """Run in interactive mode."""
    print_banner()

    while True:
        choice = main_menu()

        if choice == "1":
            wizard = SetupWizard()
            result = wizard.run_cli()
            if result:
                print("\n  Setup complete! You can now collect data or start training.")
                input("  Press Enter to continue...")

        elif choice == "2":
            print("\n  [Data Collection]")
            print("  Starting data collection...")
            print("  - Press F9 to start recording")
            print("  - Press F10 to stop recording")
            print("  - Play the game naturally")
            input("\n  Press Enter to start collection (or Ctrl+C to cancel)...")
            # TODO: Integrate actual data collection

        elif choice == "3":
            print("\n  [Training]")
            print("  Loading training configuration...")
            # TODO: Integrate training with curriculum

        elif choice == "4":
            print("\n  [Inference]")
            print("  Loading inference engine...")
            print("  - Press F11 to toggle bot")
            print("  - Press F12 for emergency stop")
            # TODO: Integrate inference

        elif choice == "5":
            print("\n  [Settings]")
            print("  Opening settings editor...")
            # TODO: Settings UI

        elif choice == "6":
            print("\n  Goodbye!")
            break

        else:
            print("\n  Invalid choice. Please try again.")


def run_wizard():
    """Run setup wizard only."""
    print_banner()
    wizard = SetupWizard()
    return wizard.run_cli()


def quick_start(game_shorthand: str):
    """Quick start for a known game."""
    # Map shorthands to game IDs
    game_map = {
        "wow": "world_of_warcraft",
        "gw2": "guild_wars_2",
        "ff14": "final_fantasy_xiv",
        "ffxiv": "final_fantasy_xiv",
        "la": "lost_ark",
        "nw": "new_world",
    }

    game_id = game_map.get(game_shorthand.lower())
    if not game_id:
        print(f"Unknown game shorthand: {game_shorthand}")
        print(f"Available: {', '.join(game_map.keys())}")
        return None

    print_banner()
    print(f"\n  Quick Start for: {game_id.replace('_', ' ').title()}")

    wizard = SetupWizard()
    wizard.start()

    # Auto-select game
    result = wizard.set_game(game_id)
    print(f"\n  Game: {result['game_name']}")

    # Default to combat task
    result = wizard.set_task("combat")
    print(f"  Task: combat")
    print(f"  Model: {result['recommended']['name']}")

    wizard.set_model(result["recommended"]["id"])
    wizard.get_data_guidance()
    wizard.set_training_config()

    # Show review and finish
    review = wizard.get_review()
    print(f"\n  Configuration:")
    print(f"    Hardware: {review['hardware']['tier'].upper()}")
    print(f"    Input Size: {review['model']['input_size']}")
    print(f"    Temporal Frames: {review['model']['temporal_frames']}")

    return wizard.finish()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="BOT-MMORPG-AI Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launcher/main.py              # Interactive mode
  python launcher/main.py --wizard     # Setup wizard only
  python launcher/main.py --quick wow  # Quick start for WoW
  python launcher/main.py --quick gw2  # Quick start for GW2
        """,
    )

    parser.add_argument(
        "--wizard",
        action="store_true",
        help="Run setup wizard only",
    )

    parser.add_argument(
        "--quick",
        metavar="GAME",
        help="Quick start for a game (wow, gw2, ff14, la, nw)",
    )

    args = parser.parse_args()

    if args.quick:
        result = quick_start(args.quick)
        if result:
            print("\n  Quick setup complete!")
            for step in result["next_steps"]:
                print(f"    {step}")
    elif args.wizard:
        run_wizard()
    else:
        run_interactive()


if __name__ == "__main__":
    main()
