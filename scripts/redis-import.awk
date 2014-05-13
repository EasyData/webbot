#!/usr/bin/awk -f

{
    printf("*%d\r\n", NF);
    for(i=1;i<=NF;i++)
        printf("$%d\r\n%s\r\n", length($i), $i);
}

