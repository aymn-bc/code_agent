class TicTacToe:
    def __init__(self):
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'

    def print_board(self):
        for row in self.board:
            print(' | '.join(row))
            print('-' * 9)

    def make_move(self, row, col):
        if self.board[row][col] == ' ':
            self.board[row][col] = self.current_player
            return True
        else:
            print("Cell already occupied. Try again.")
            return False

    def check_winner(self):
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != ' ':
                return True

        for j in range(3):
            if self.board[0][j] == self.board[1][j] == self.board[2][j] != ' ':
                return True

        if (self.board[0][0] == self.board[1][1] == self.board[2][2] != ' ') or \
           (self.board[0][2] == self.board[1][1] == self.board[2][0] != ' '):
            return True

        return False

    def is_full(self):
        for row in self.board:
            if ' ' in row:
                return False
        return True

    def play_game(self):
        while not self.is_full() and not self.check_winner():
            self.print_board()
            print(f"Player {self.current_player}'s turn.")
            row = int(input("Enter row (0-2): "))
            col = int(input("Enter column (0-2): "))

            if not self.make_move(row, col):
                continue

            if self.check_winner():
                self.print_board()
                print(f"Player {self.current_player} wins!")
                break
            elif self.is_full():
                self.print_board()
                print("It's a tie!")
                break

            self.current_player = 'O' if self.current_player == 'X' else 'X'

if __name__ == "__main__":
    game = TicTacToe()
    game.play_game()