extern int __VERIFIER_nondet_int(void);

int main() {
    int k, y, x, c;
    k = __VERIFIER_nondet_int();

    y = 0;
    x = 0;
    c = 0;

    while (1) {
        // __VERIFIER_assert(6*y*y*y*y*y + 15*y*y*y*y + 10*y*y*y - 30*x - y == 0);

        if (!(c + 6*y*y*y*y*y + 15*y*y*y*y + 10*y*y*y - 30*x - y < k))
            break;

        c = c + 1;
        y = y + 1;
        x = y * y * y * y + x;
    }

    // __VERIFIER_assert(6*y*y*y*y*y + 15*y*y*y*y + 10*y*y*y - 30*x - y == 0);
    // __VERIFIER_assert(k*y == y*y);
    return 0;
}
