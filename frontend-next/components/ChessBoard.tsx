import { Chess } from 'chess.js';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Chessboard } from 'react-chessboard';
import Engine from '../public/stockfish/engine';

const ChessBoard: React.FC = () => {
  const engine = useMemo(() => new Engine(), []);
  const game = useMemo(() => new Chess(), []);
  const [gamePosition, setGamePosition] = useState(game.fen());
  const [boardWidth, setBoardWidth] = useState(0);
  const boardContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        const { width, height } = entry.contentRect;
        // Set board size to 90% of the smallest dimension of the container
        const newSize = Math.min(width, height) * 0.9;
        setBoardWidth(newSize);
      }
    });

    if (boardContainerRef.current) {
      observer.observe(boardContainerRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, []);

  function findBestMove() {
    engine.evaluatePosition(game.fen());
    engine.onMessage(({
      bestMove
    }) => {
      if (bestMove) {
        game.move({
          from: bestMove.substring(0, 2),
          to: bestMove.substring(2, 4),
          promotion: bestMove.substring(4, 5)
        });
        setGamePosition(game.fen());
      }
    });
  }

  function onDrop(sourceSquare: string, targetSquare: string, piece: string) {
    const move = game.move({
      from: sourceSquare,
      to: targetSquare,
      promotion: piece[1].toLowerCase() ?? "q"
    });
    setGamePosition(game.fen());

    // illegal move
    if (move === null) return false;

    // exit if the game is over
    if (game.isGameOver() || game.isDraw()) return false;
    findBestMove();
    return true;
  }

  const [activeSquare, setActiveSquare] = useState("");

  const threeDPieces = useMemo(() => {
    const pieces = [{
      piece: "wP",
      pieceHeight: 1
    }, {
      piece: "wN",
      pieceHeight: 1.2
    }, {
      piece: "wB",
      pieceHeight: 1.2
    }, {
      piece: "wR",
      pieceHeight: 1.2
    }, {
      piece: "wQ",
      pieceHeight: 1.5
    }, {
      piece: "wK",
      pieceHeight: 1.6
    }, {
      piece: "bP",
      pieceHeight: 1
    }, {
      piece: "bN",
      pieceHeight: 1.2
    }, {
      piece: "bB",
      pieceHeight: 1.2
    }, {
      piece: "bR",
      pieceHeight: 1.2
    }, {
      piece: "bQ",
      pieceHeight: 1.5
    }, {
      piece: "bK",
      pieceHeight: 1.6
    }];
    const pieceComponents: Record<string, any> = {};
    pieces.forEach(({
      piece,
      pieceHeight
    }) => {
      pieceComponents[piece] = ({
        squareWidth,
        square
      }: { squareWidth: number; square: string }) => <div style={{
        width: squareWidth,
        height: squareWidth,
        position: "relative",
        pointerEvents: "none"
      }}>
          <img src={`/3d-pieces/${piece}.webp`} width={squareWidth} height={pieceHeight * squareWidth} style={{
          position: "absolute",
          bottom: `${0.2 * squareWidth}px`,
          objectFit: piece[1] === "K" ? "contain" : "cover"
        }} />
        </div>;
    });
    return pieceComponents;
  }, []);

  const boardWrapperStyle = {
    width: '100%',
    height: '100%',
    display: 'flex',
    flexDirection: 'column' as const,
    justifyContent: 'center',
    alignItems: 'center',
    flex: 1,
    minHeight: 0,
    paddingBottom: '8rem',
    boxSizing: 'border-box' as const,
  };

  const buttonStyle = {
    padding: "0.5rem 1rem",
    margin: "0 0.5rem",
    backgroundColor: "#4a5568",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "0.875rem"
  };

  // Cleanup engine on unmount
  useEffect(() => {
    return () => {
      engine.terminate();
    };
  }, [engine]);

  return (
    <div ref={boardContainerRef} style={boardWrapperStyle}>
      <div style={{
        display: "flex",
        justifyContent: "center",
        marginBottom: '1rem',
      }}>
        <button style={buttonStyle} onClick={() => {
          game.reset();
          setGamePosition(game.fen());
        }}>
          Reset
        </button>
        <button style={buttonStyle} onClick={() => {
          game.undo();
          game.undo();
          setGamePosition(game.fen());
        }}>
          Undo
        </button>
      </div>
      {boardWidth > 0 && (
        <div style={{ marginTop: '-10px' }}>
          <style jsx>{`
            :global([data-boardid="Styled3DBoard"] > div) {
              margin-top: -3px !important;
              margin-left: -10px !important;
            }
          `}</style>
          <Chessboard
            id="Styled3DBoard"
            position={gamePosition}
            onPieceDrop={onDrop}
            boardWidth={boardWidth}
            customBoardStyle={{
              transform: "rotateX(27.5deg)",
              transformOrigin: "center",
              border: "16px solid #b8836f",
              borderStyle: "outset",
              borderRightColor: " #b27c67",
              borderRadius: "4px",
              boxShadow: "rgba(0, 0, 0, 0.5) 2px 24px 24px 8px",
              borderRightWidth: "16px",
              borderLeftWidth: "16px",
              borderTopWidth: "0px",
              borderBottomWidth: "18px",
              borderTopLeftRadius: "8px",
              borderTopRightRadius: "8px",
              padding: "8px 8px 12px",
              backgroundColor: "#e0c094",
              backgroundImage: 'url("/wood-pattern.png")',
              backgroundSize: "cover",
            }}
            customPieces={threeDPieces}
            customLightSquareStyle={{
              backgroundColor: "#e0c094",
              backgroundImage: 'url("/wood-pattern.png")',
              backgroundSize: "cover"
            }} customDarkSquareStyle={{
              backgroundColor: "#865745",
              backgroundImage: 'url("/wood-pattern.png")',
              backgroundSize: "cover"
            }}
            animationDuration={500}
            customSquareStyles={{
              [activeSquare]: {
                boxShadow: "inset 0 0 1px 6px rgba(255,255,255,0.75)"
              }
            }}
            onMouseOverSquare={(sq) => setActiveSquare(sq)}
            onMouseOutSquare={() => setActiveSquare("")}
          />
        </div>
      )}
    </div>
  );
};

export default ChessBoard; 