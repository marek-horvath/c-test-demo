#include <stdio.h>
int collatz(const int number);
int main() {
    int res = collatz(6);
    if (res == 9) {
        printf("TASK:collatz=1\n");
    } else {
        printf("TASK:collatz=0\n");
    }
    return 0;
}
