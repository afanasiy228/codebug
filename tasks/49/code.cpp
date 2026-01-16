#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string t,p;
    if(!(cin>>t>>p)) return 0;
    size_t pos=t.find(p);
    if(pos==string::npos) cout<<-1<<"\n";
    else cout<<pos<<"\n";

}
