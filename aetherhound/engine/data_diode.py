"""
Air-Gapped Optical Data Diode Simplex Transmitter with Forward Error Correction (FEC).
Transmits unidirectional UDP telemetry datagrams across hardware simplex optical diodes.
Uses block-level XOR parity encoding to recover dropped packets without a return acknowledgement path.
"""

import json
import zlib
from typing import List, Optional


class DataDiodePacket:
    """Structured packet frame for simplex data diode transmission."""

    def __init__(self, block_id: int, seq_id: int, total_in_block: int, payload: bytes, is_parity: bool = False):
        self.block_id = block_id
        self.seq_id = seq_id
        self.total_in_block = total_in_block
        self.payload = payload
        self.is_parity = is_parity

    def encode(self) -> bytes:
        """Serialize frame with CRC32 checksum."""
        header = {
            "b": self.block_id,
            "s": self.seq_id,
            "n": self.total_in_block,
            "p": 1 if self.is_parity else 0
        }
        header_bytes = json.dumps(header).encode("utf-8")
        header_len = len(header_bytes)
        body = header_len.to_bytes(2, "big") + header_bytes + self.payload
        crc = zlib.crc32(body)
        return crc.to_bytes(4, "big") + body

    @classmethod
    def decode(cls, data: bytes) -> Optional["DataDiodePacket"]:
        """Parse raw frame and verify CRC32."""
        if len(data) < 6:
            return None
        expected_crc = int.from_bytes(data[:4], "big")
        body = data[4:]
        if zlib.crc32(body) != expected_crc:
            return None
        header_len = int.from_bytes(body[:2], "big")
        header_bytes = body[2:2 + header_len]
        payload = body[2 + header_len:]
        header = json.loads(header_bytes.decode("utf-8"))
        return cls(
            block_id=header["b"],
            seq_id=header["s"],
            total_in_block=header["n"],
            payload=payload,
            is_parity=bool(header["p"])
        )


class DataDiodeTransmitter:
    """
    Encodes and transmits telemetry blocks over simplex UDP links with XOR parity FEC.
    """

    def __init__(self, block_size: int = 4):
        self.block_size = block_size
        self.current_block_id = 0

    def encode_message_block(self, message: str) -> List[DataDiodePacket]:
        """Split message into data packets and append an XOR parity FEC packet."""
        raw_bytes = message.encode("utf-8")
        chunk_len = max(1, (len(raw_bytes) + self.block_size - 1) // self.block_size)
        chunks = []
        for i in range(self.block_size):
            start = i * chunk_len
            end = min(len(raw_bytes), (i + 1) * chunk_len)
            chunk = raw_bytes[start:end] if start < len(raw_bytes) else b""
            chunks.append(chunk)

        max_chunk_size = max(len(c) for c in chunks)
        padded_chunks = [c.ljust(max_chunk_size, b"\x00") for c in chunks]

        # Compute XOR parity block
        parity = bytearray(max_chunk_size)
        for chunk in padded_chunks:
            for idx, b in enumerate(chunk):
                parity[idx] ^= b

        packets = []
        for seq, chunk in enumerate(padded_chunks):
            packets.append(DataDiodePacket(
                block_id=self.current_block_id,
                seq_id=seq,
                total_in_block=self.block_size,
                payload=chunk,
                is_parity=False
            ))
        packets.append(DataDiodePacket(
            block_id=self.current_block_id,
            seq_id=self.block_size,
            total_in_block=self.block_size,
            payload=bytes(parity),
            is_parity=True
        ))
        self.current_block_id += 1
        return packets

    @staticmethod
    def recover_block(received_packets: List[DataDiodePacket]) -> Optional[str]:
        """Reconstruct block data using XOR parity if at most 1 packet was dropped."""
        if not received_packets:
            return None
        total = received_packets[0].total_in_block
        seq_map = {p.seq_id: p.payload for p in received_packets}

        missing = [i for i in range(total) if i not in seq_map]
        if len(missing) == 0:
            combined = b"".join(seq_map[i] for i in range(total))
            return combined.rstrip(b"\x00").decode("utf-8")
        elif len(missing) == 1 and total in seq_map:
            missing_idx = missing[0]
            parity = bytearray(seq_map[total])
            for i in range(total):
                if i != missing_idx:
                    for idx, b in enumerate(seq_map[i]):
                        parity[idx] ^= b
            seq_map[missing_idx] = bytes(parity)
            combined = b"".join(seq_map[i] for i in range(total))
            return combined.rstrip(b"\x00").decode("utf-8")
        return None
