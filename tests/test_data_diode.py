"""
Unit tests for Air-Gapped Optical Data Diode Simplex Transmitter and FEC Parity Recovery.
"""

import pytest
from aetherhound.engine.data_diode import DataDiodePacket, DataDiodeTransmitter


def test_packet_encode_decode_crc():
    pkt = DataDiodePacket(block_id=1, seq_id=0, total_in_block=4, payload=b"AETHERHOUND_ALERT")
    encoded = pkt.encode()
    decoded = DataDiodePacket.decode(encoded)
    assert decoded is not None
    assert decoded.block_id == 1
    assert decoded.seq_id == 0
    assert decoded.payload == b"AETHERHOUND_ALERT"


def test_packet_crc_corruption_detection():
    pkt = DataDiodePacket(block_id=1, seq_id=0, total_in_block=4, payload=b"VALID")
    encoded = bytearray(pkt.encode())
    encoded[-1] ^= 0xFF
    decoded = DataDiodePacket.decode(bytes(encoded))
    assert decoded is None


def test_fec_parity_packet_loss_recovery():
    tx = DataDiodeTransmitter(block_size=4)
    msg = "INCIDENT: RACK-03 ACOUSTIC_PWM EXFIL TRACED"
    packets = tx.encode_message_block(msg)
    assert len(packets) == 5

    # Simulate dropping packet at seq_id = 2
    dropped = [p for p in packets if p.seq_id != 2]
    recovered = DataDiodeTransmitter.recover_block(dropped)
    assert recovered == msg
