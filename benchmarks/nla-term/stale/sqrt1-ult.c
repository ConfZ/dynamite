// https://github.com/sosy-lab/sv-benchmarks/blob/master/c/nla-digbench/sqrt1.c
/* Compute the floor of the square root of a natural number */
extern void __VERIFIER_error() __attribute__ ((__noreturn__));

extern void abort(void); 
void reach_error(){}
extern int __VERIFIER_nondet_int(void);
extern void abort(void); 
void assume_abort_if_not(int cond) { 
  if(!cond) {abort();}
}
void __VERIFIER_assert(int cond) {
    if (!(cond)) {
    ERROR:
        {reach_error();abort();}
    }
    return;
}

void __VERIFIER_assert1(int cond) {
    if (!(cond)) {
	ERROR: __VERIFIER_error();
    }
    return;
}



int main() {
    int n, a, s, t;
    n = __VERIFIER_nondet_int();

    a = 0;
    s = 1;
    t = 1;

    while (s <= n) {
	__VERIFIER_assert1(t == 2*a + 1);
	__VERIFIER_assert1(s == (a + 1) * (a + 1));
	__VERIFIER_assert1(t*t - 4*s + 2*t + 1 == 0);
        // the above 2 should be equiv to 
      //if (!(s <= n))break;
        a = a + 1;
        t = t + 2;
        s = s + t;
    }
    
    //__VERIFIER_assert(t == 2 * a + 1);
    //__VERIFIER_assert(s == (a + 1) * (a + 1));
    //__VERIFIER_assert(t*t - 4*s + 2*t + 1 == 0);

    return 0;
}
