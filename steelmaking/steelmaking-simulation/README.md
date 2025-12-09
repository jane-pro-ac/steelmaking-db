# Steelmaking Simulation

A Python program that simulates steelmaking operations by generating realistic data for the steelmaking_operation table.

## Features

- Simulates the BOF -> LF -> CCM steelmaking process flow
- Generates realistic timestamps with proper sequencing
- Manages multiple equipment units (3 BOF, 3 LF, 3 CCM)
- Runs continuously to simulate real-time data generation
- Follows all business rules for operation status and timing

## Prerequisites

- Python 3.10+
- Poetry
- PostgreSQL database with the steelmaking schema

## Installation

```bash
# Install dependencies
poetry install

# Copy environment file and configure
cp .env.example .env
# Edit .env with your database credentials
```

## Usage

```bash
# Run the simulation
poetry run simulate

# Or activate the virtual environment first
poetry shell
python -m steelmaking_simulation.main
```

## Configuration

Edit the `.env` file to configure:

- Database connection settings
- Simulation interval (seconds between ticks)
- Probability of starting new heats

## Process Flow

The simulation follows the steelmaking process:
1. **BOF (G12)**: Basic Oxygen Furnace - Initial steel production
2. **LF (G13)**: Ladle Furnace - Secondary refining
3. **CCM (G16)**: Continuous Casting Machine - Final casting

## Rules

- Operation duration: 10-30 minutes
- Gap between operations: 1-10 minutes
- Status flow: pending -> active -> completed
- Sequential process: BOF must complete before LF can start, etc.
