#include<stdio.h>

void vtrace1( int x, int y) {
}

void vtrace2(int x, int y) {
}

void vtrace3(int x, int y) {
}

// void vtrace4(int x0, int y0, int x1, int y1) {
// }

void mainQ_loop(int x, int y) {
  vtrace1(x, y);

  while (x >= 0) {
    vtrace2(x, y);

    // int x0 = x;
    // int y0 = y;

    x = x + y;

    // int x1 = x;
    // int y1 = y;
    // vtrace4(x0, y0, x1, y1);
  }
  vtrace3(x, y);
}

int main() {
  //mainQ(1, 2);
  return 0;
}

/*
  // The original code
  while (x >= 0) {
    x = x + y;
    y = y + 1;
  }
 */

