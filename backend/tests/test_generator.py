"""
Tests for DataGenerator and dataset seeding reproducibility.
"""
from __future__ import annotations

import pytest
from app.generator.orchestrator import DataGenerator, SCALE_CONFIG


def test_starter_generation_counts():
    """Verify generated counts match scale configuration for starter dataset."""
    gen = DataGenerator(seed=20261022, scale="starter")
    data = gen.generate_all()

    assert len(data["customers"]) == SCALE_CONFIG["starter"]["customers"]
    assert len(data["products"]) == SCALE_CONFIG["starter"]["products"]
    assert len(data["orders"]) == SCALE_CONFIG["starter"]["orders"]
    assert len(data["complaints"]) == SCALE_CONFIG["starter"]["complaints"]
    assert len(data["messages"]) >= SCALE_CONFIG["starter"]["messages"]
    assert len(data["teams"]) == 6
    assert len(data["agents"]) == 12  # 6 teams * 2 agents


def test_identical_seed_reproducibility():
    """Two generation runs with the identical seed must generate exact matching records."""
    gen1 = DataGenerator(seed=20261022, scale="starter")
    data1 = gen1.generate_all()

    gen2 = DataGenerator(seed=20261022, scale="starter")
    data2 = gen2.generate_all()

    # Compare first customer
    assert data1["customers"][0] == data2["customers"][0]
    # Compare first complaint
    assert data1["complaints"][0] == data2["complaints"][0]
    # Compare first order
    assert data1["orders"][0] == data2["orders"][0]
    # Compare total counts across all entities
    for key in data1:
        assert len(data1[key]) == len(data2[key])


def test_different_seeds_produce_variation():
    """Different seeds should generate distinct customer and complaint values."""
    gen1 = DataGenerator(seed=11111, scale="starter")
    data1 = gen1.generate_all()

    gen2 = DataGenerator(seed=22222, scale="starter")
    data2 = gen2.generate_all()

    assert data1["customers"][0]["email"] != data2["customers"][0]["email"]
    assert data1["complaints"][0]["subject"] != data2["complaints"][0]["subject"]
