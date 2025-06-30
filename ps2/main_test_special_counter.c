#include <stdio.h>
unsigned long special_counter(const int input_array[], const int arrays_size);
int main() {
    int arr[6] = {1, 2, 3, 4, 5, 6};
    unsigned long res = special_counter(arr, 6);
    if (res == 92) {
        printf("TASK:special_counter=1\n");
    } else {
        printf("TASK:special_counter=0\n");
    }
    return 0;
}
