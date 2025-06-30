#include <stdio.h>
int opposite_number(const int n, const int number);
int main() {
    int res = opposite_number(12, 9);
    if (res == 3) {
        printf("TASK:opposite_number=1\n");
    } else {
        printf("TASK:opposite_number=0\n");
    }
    return 0;
}
