#include <stdio.h>
unsigned long sum_squared(const int line);
int main() {
    unsigned long res = sum_squared(4);
    if (res == 41) {
        printf("TASK:sum_squared=1\n");
    } else {
        printf("TASK:sum_squared=0\n");
    }
    return 0;
}
