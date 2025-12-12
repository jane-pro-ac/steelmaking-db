"""Main entry point for the steelmaking simulation."""

import logging
import sys

from .config import DatabaseConfig, SimulationConfig
from .simulator import SteelmakingSimulator


def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("Steelmaking Operation Simulator")
    logger.info("=" * 60)
    
    # Load configurations
    db_config = DatabaseConfig()
    sim_config = SimulationConfig()
    
    logger.info(f"Database: {db_config.host}:{db_config.port}/{db_config.database}")
    logger.info(f"Simulation interval: {sim_config.interval}s")
    logger.info(f"New heat probability: {sim_config.new_heat_probability}")
    logger.info("-" * 60)
    
    # Create and run simulator
    simulator = SteelmakingSimulator(db_config, sim_config)
    
    try:
        simulator.run()
    except Exception as e:
        logger.error(f"Simulation error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
