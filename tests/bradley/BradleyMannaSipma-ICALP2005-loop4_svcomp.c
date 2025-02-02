/*
 * Program used in the experimental evaluation of the following paper.
 * 2008ESOP - Chawdhary,Cook,Gulwani,Sagiv,Yang - Ranking Abstractions
 *
 * Date: 2014
 * Author: Caterina Urban
 */

typedef enum {false, true} bool;

extern int __VERIFIER_nondet_int(void);

int main() {
    int i, j, k, an, bn, tk;
	i = __VERIFIER_nondet_int();
	j = __VERIFIER_nondet_int();
	k = __VERIFIER_nondet_int();
	an = __VERIFIER_nondet_int();
	bn = __VERIFIER_nondet_int();
	tk = __VERIFIER_nondet_int();
	while (((an >= i && bn >= j) || (an >= i && bn <= j) || (an <= i && bn >= j)) && k >= tk + 1) {
		if (an >= i && bn >= j) {
			if (__VERIFIER_nondet_int()) {
				j = j + k;
				tk = k;
				k = __VERIFIER_nondet_int();
			} else {
				i = i + 1;
			}
		} else {if (an >= i && bn <= j) {
			i = i + 1;
		} else {if (an <= i && bn >= j) {
			j = j + k;
			tk = k;
			k = __VERIFIER_nondet_int();
		}}}
	}
	return 0;
}
