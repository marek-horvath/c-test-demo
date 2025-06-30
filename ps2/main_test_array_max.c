#include <stdio.h>
int array_max(const int input_array[], const int arrays_size);
int main() {
    int arr[5] = {1, 5, 3, 2, 4};
    int res = array_max(arr, 5);
    if (res == 5) {
        printf("TASK:array_max=1\n");
    } else {
        printf("TASK:array_max=0\n");
    }
    return 0;
}
