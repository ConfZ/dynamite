#define f1(cc,kk) (kk-cc)
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
int main() {
    int n, a, s, t;
    int c, k;
    n = __VERIFIER_nondet_int();
    k = __VERIFIER_nondet_int();
    int tc, tk;
    int dup = 0;
    a = 0;
    s = 1;
    t = 1;
    c = 0;
    while (t*t - 4*s + 2*t + 1 + c <= k) {
        //__VERIFIER_assert(t == 2*a + 1);
        //__VERIFIER_assert(s == (a + 1) * (a + 1));
        //__VERIFIER_assert(t*t - 4*s + 2*t + 1 == 0);
        // the above 2 should be equiv to 
        if(dup) {
            if ( !(f1(tc, tk) > f1(c, k) &&  f1(tc, tk)  >= 0 )) {
                __VERIFIER_error();
            }
        }
        if(!dup && __VERIFIER_nondet_int()) { 
          tc = c; tk = k; dup = 1; }
        a = a + 1;
        t = t + 2;
        s = s + t;
        c = c + 1;
    }
    //__VERIFIER_assert(t == 2 * a + 1);
    //__VERIFIER_assert(s == (a + 1) * (a + 1));
    //__VERIFIER_assert(t*t - 4*s + 2*t + 1 == 0);
    return 0;
}
