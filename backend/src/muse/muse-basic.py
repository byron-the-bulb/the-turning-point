from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

def test_muse_s_connectivity():
    params = BrainFlowInputParams()
    params.mac_address = ""  # Leave empty unless you know the Muse S MAC address
    board = BoardShim(BoardIds.MUSE_S_BOARD, params)

    try:
        board.prepare_session()
        print("Connected successfully to Muse S via Brainflow")
        board.release_session()
        return True
    except Exception as e:
        print(f"Failed to connect: {str(e)}")
        return False

if __name__ == "__main__":
    test_muse_s_connectivity()