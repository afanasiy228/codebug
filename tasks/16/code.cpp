#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int q;
    if(!(cin>>q)) return 0;

    deque<long long> dq;
    queue<long long> qu;

    while(q--) {

        string op;
        cin>>op;

        if(op=="push") {
            long long x;
            cin>>x;
            qu.push(x);

            while(!dq.empty() && dq.back() < x) dq.pop_back();

            dq.push_back(x);

        }
        else if(op=="pop") {
            if(!qu.empty()) {

                long long x = qu.front();
                qu.pop();

                if(!dq.empty() && dq.front()==x) dq.pop_front();

            }
        }
        else if(op=="max") {
            if(dq.empty()) cout<<"0\n";
            else cout<<dq.back()<<"\n";

        }

    }

}
