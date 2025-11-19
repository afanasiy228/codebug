Your friend, Jackson is invited to a TV show called SuperMemo in which the participant is told to play a memorizing game. At first, the host tells the participant a sequence of numbers, {𝐴1,𝐴2,…𝐴𝑛}. Then the host performs a series of operations and queries on the sequence which consists:

𝐴𝐷𝐷 𝑥 𝑦 𝐷: Add 𝐷 to each number in sub-sequence {𝐴𝑥…𝐴𝑦}. For example, performing "𝐴𝐷𝐷 2 4 1" on {1,2,3,4,5} results in {1,3,4,5,5}
𝑅𝐸𝑉𝐸𝑅𝑆𝐸 𝑥 𝑦: reverse the sub-sequence 𝐴𝑥…𝐴𝑦. For example, performing "𝑅𝐸𝑉𝐸𝑅𝑆𝐸 2 4" on {1,2,3,4,5} results in {1,4,3,2,5}
𝑅𝐸𝑉𝑂𝐿𝑉𝐸 𝑥 𝑦 𝑇: rotate sub-sequence 𝐴𝑥…𝐴𝑦 𝑇 times. For example, performing "𝑅𝐸𝑉𝑂𝐿𝑉𝐸 2 4 2" on {1,2,3,4,5} results in {1,3,4,2,5}
𝐼𝑁𝑆𝐸𝑅𝑇 𝑥 𝑃: insert 𝑃 after 𝐴𝑥. For example, performing "𝐼𝑁𝑆𝐸𝑅𝑇 2 4" on {1,2,3,4,5} results in {1,2,4,3,4,5}
𝐷𝐸𝐿𝐸𝑇𝐸 𝑥: delete 𝐴𝑥. For example, performing "𝐷𝐸𝐿𝐸𝑇𝐸 2" on {1,2,3,4,5} results in {1,3,4,5}
𝑀𝐼𝑁 𝑥 𝑦: query the participant what is the minimum number in sub-sequence {𝐴𝑥…𝐴𝑦}. For example, the correct answer to "𝑀𝐼𝑁 2 4" on {1,2,3,4,5} is 2
To make the show more interesting, the participant is granted a chance to turn to someone else that means when Jackson feels difficult in answering a query he may call you for help. You task is to watch the TV show and write a program giving the correct answer to each query in order to assist Jackson whenever he calls.

Input
The first line contains 𝑛 (𝑛≤100000).

The following 𝑛 lines describe the sequence.

Then follows 𝑀 (𝑀≤100000), the numbers of operations and queries.

The following 𝑀 lines describe the operations and queries.

Output
For each "𝑀𝐼𝑁" query, output the correct answer.