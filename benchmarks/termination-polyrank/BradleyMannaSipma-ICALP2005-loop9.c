
typedef enum {false, true} bool;

extern int __VERIFIER_nondet_int(void);

int main() {
    	int y1, y2;
	y1 = __VERIFIER_nondet_int();
	y2 = __VERIFIER_nondet_int();
	if (y1 >= 1 && y2 >= 1) {
		while (y1 != y2) {
			if (y1 >= y2 + 1) {
				y1 = y1 - y2;
    			} else {
	    			y2 = y2 - y1;
			} //else {
				//break;
			//}
		}
	}
	return 0;
}
