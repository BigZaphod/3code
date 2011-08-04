//--------------------------------------------
// 3code programming language
// by: BigZaphod sean@fifthace.com
// http://www.bigzaphod.org/3code/
// 
// License: Public Domain
//--------------------------------------------

#include <iostream>
#include <fstream>
#include <string>
#include <set>
#include <vector>
#include <list>
#include <sstream>
using namespace std;

set<char> specialTokens;
typedef list<string> token_list;

class token_sequence {
public:
    token_list tokens;

    token_sequence()                      {}
    token_sequence( const token_list& l ) { append(l); }
    void append( const token_list& l )    { tokens.insert(tokens.end(),l.begin(),l.end()); }
    void append( string tok )             { tokens.push_back(tok); }
    void clear()                          { tokens.clear(); }
    bool empty() const                    { return tokens.empty(); }
    string cur() const                    { return tokens.front(); }
    bool next()                           { if(!empty()) tokens.pop_front(); return !empty(); }
    bool isNext( string t ) const         { if(tokens.size()<=1) return false; return t==*(++tokens.begin()); }
};

class func_def {
public:
    func_def() : args(0) {}
    func_def(string s, unsigned int n, const token_sequence& b=token_sequence()) : args(n), name(s), body(b) {}
    func_def(const func_def& f) { *this=f; }
    func_def& operator=(const func_def& f) {
        args = f.args;
        name = f.name;
        body = f.body;
        return *this;
    }
    bool operator<(const func_def& f) const {
        if( name < f.name ) return true;
        return (name==f.name) && (args<f.args);
    }

    unsigned int args;
    string name;
    token_sequence body;
};

typedef set<func_def> func_set;
func_set definedFunctions;

double currentValue;

class stack_frame {
    public:
    stack_frame() : v1(0), v2(0), v3(0) {}
    double v1, v2, v3;
};

vector<stack_frame> scope;

template <typename T, typename S>
T stream_cast(S const& val) {
    std::stringstream stream;
    stream << val;
    T rc;
    stream >> rc;
    return rc;
}

void interpret( token_sequence& seq );  // proto

void initSystem() {
    currentValue = 0;
    scope.resize(1);  // global scope

    definedFunctions.insert( func_def(">",2) );
    definedFunctions.insert( func_def("<",2) );
    definedFunctions.insert( func_def("=",2) );
    definedFunctions.insert( func_def(">=",2) );
    definedFunctions.insert( func_def("<=",2) );
    definedFunctions.insert( func_def("+",2) );
    definedFunctions.insert( func_def("-",2) );
    definedFunctions.insert( func_def("*",2) );
    definedFunctions.insert( func_def("/",2) );
    definedFunctions.insert( func_def("print",1) );
    definedFunctions.insert( func_def("write",1) );
    definedFunctions.insert( func_def("println",1) );
    definedFunctions.insert( func_def("nl",0) );

    specialTokens.insert( '=' );
    specialTokens.insert( '[' );
    specialTokens.insert( ']' );
    specialTokens.insert( '?' );
}

token_list getTokens( string src ) {
    token_list toks;
    string work;

    for( unsigned int i=0; i<src.length(); i++ ) {
        if( isspace(src[i]) ) {
            if( !work.empty() ) {
                toks.push_back(work);
                work = "";
            }
        } else if( specialTokens.count(src[i]) ) {
            if( !work.empty() ) {
                toks.push_back(work);
                work = "";
            }
            work.append(1, src[i]);
            toks.push_back(work);
            work = "";
        } else {
            work.append(1, src[i]);
        }
    }

    if( !work.empty() )
        toks.push_back(work);

    return toks;
}

bool isVariable( string tag ) {
    return (tag=="x") || (tag=="y") || (tag=="z")
        || (tag=="i") || (tag=="j") || (tag=="k");
}

double variableValue( string tag ) {
    if( tag=="x" ) return scope.front().v1;
    if( tag=="y" ) return scope.front().v2;
    if( tag=="y" ) return scope.front().v3;

    if( tag=="i" ) return scope.back().v1;
    if( tag=="j" ) return scope.back().v2;
    if( tag=="k" ) return scope.back().v3;

    // error shouldn't happen!
    cout << "WARNING: Invalid variable reference." << endl;
    return 0;
}

void setVariable( string tag, double val ) {
    if( tag=="x" ) { scope.front().v1 = val; return; }
    if( tag=="y" ) { scope.front().v2 = val; return; }
    if( tag=="z" ) { scope.front().v3 = val; return; }

    if( tag=="i" ) { scope.back().v1 = val; return; }
    if( tag=="j" ) { scope.back().v2 = val; return; }
    if( tag=="k" ) { scope.back().v3 = val; return; }

    // should never ever happen...
    cout << "WARNING: Invalid variable assignment." << endl;
}

bool isNumber( string str ) {
    unsigned int i=0;
    if( !str.empty() && (str[i]=='-' || str[i] =='+') ) i++;
    return string::npos == str.find_first_not_of( ".eE0123456789", i );
}

bool opAssignment( token_sequence& seq ) {
    // first skip = which we know is already there
    if( !seq.next() ) {
        cout << "ERROR: Assignment incomplete." << endl;
        return false;
    }
    if( !isVariable(seq.cur()) ) {
        cout << "ERROR: Assignment to non-variable." << endl;
        return false;
    }
    setVariable(seq.cur(), currentValue);
    seq.next();
    return true;
}

bool opThen( token_sequence& seq ) {
    // Test currentValue.  If true, just return (execution will continue in interpret's loop).
    // otherwise, consume tokens until we hit either else or ?.  (consume them both, too)
    if( currentValue==0 ) {
        bool done=false;
        while( !done && seq.next() )
            done = (seq.cur()=="?") || (seq.cur()=="else");

        if( !done ) {
            cout << "ERROR: Conditional incomplete." << endl;
            return false;
        }
    }

    seq.next();  // consumes "then" if condition is true, or "else" or "?" otherwise
    return true;
}

bool opElse( token_sequence& seq ) {
    // we should only encounter an "else" if the condition was true, which means
    // all we must do is skip to the terminating "?".
    bool found=false;
    while( seq.next() && !found )
        found = (seq.cur()=="?");
    return found;
}

bool callFunction( string func, vector<double> args ) {
    func_set::iterator f = definedFunctions.find(func_def(func,args.size()));
    if( f == definedFunctions.end() ) {
        cout << "ERROR: No function '" << func << "' with support for " << args.size() << " argument(s)." << endl;
        return false;
    }

    // if no body code, then let's assume it is a system function
    if( f->body.empty() ) {
        if( f->name=="+" )          currentValue = args[0] + args[1];
        else if( f->name=="-" )     currentValue = args[0] - args[1];
        else if( f->name=="*" )     currentValue = args[0] * args[1];
        else if( f->name=="/" )     currentValue = args[0] / args[1];
        else if( f->name=="print")  cout << args[0];
        else if( f->name=="println")cout << args[0] << endl;
        else if( f->name=="nl")     cout << endl;
        else if( f->name=="write")  cout << (char)args[0];
        else if( f->name=="<" )     currentValue = args[0] < args[1];
        else if( f->name==">" )     currentValue = args[0] > args[1];
        else if( f->name=="=" )     currentValue = args[0] == args[1];
        else if( f->name=="<=" )    currentValue = args[0] <= args[1];
        else if( f->name==">=" )    currentValue = args[0] >= args[1];
    } else {
        // setup scope
        scope.push_back( stack_frame() );
        switch(args.size()) {
            default:
            case 3:     scope.back().v3=args[2];
            case 2:     scope.back().v2=args[1];
            case 1:     scope.back().v1=args[0];
            case 0:     break;  // nothing
        };

        // run body
        // first make copy because tokens are consumed
        token_sequence run = f->body;
        interpret(run);

        // trash scope
        scope.pop_back();
    }

    return true;
}

bool interpStatement( token_sequence& seq ) {
    bool ok = true;

    if( isVariable(seq.cur()) )
        currentValue = variableValue(seq.cur());
    else if( seq.isNext("[") ) {
        vector<double> arguments;
        string func = seq.cur();
        seq.next();     // skip past function name
        seq.next();     // causes a skip of [

        while( ok=!seq.empty() ) {
            if( seq.cur()=="]" ) break;     // note, the ']' is removed at the end of this function!
            ok = interpStatement(seq);
            arguments.push_back(currentValue);
        }

        if( ok ) {
            ok = callFunction(func, arguments);
        } else {
            cout << "ERROR: Incomplete statement." << endl;
            ok = false;
        }
    }
    else if( isNumber(seq.cur()) )
        currentValue = stream_cast<double>(seq.cur());
    else {
        cout << "ERROR: Unknown token '" << seq.cur() << "'." << endl;
        ok = false;
    }

    seq.next();
    return ok;
}

bool defineFunction( token_sequence& seq ) {
    func_def func;

    // extract function name
    if( !seq.next() ) goto badfunc;
    func.name = seq.cur();

    // extract arguments
    if( !seq.next() ) goto badfunc;
    func.args = stream_cast<unsigned int>(seq.cur());
    if( func.args>3 ) goto badfunc;

    // seek the end of the function (we don't validate here, really)
    while( seq.next() && !seq.isNext("F") )
        func.body.append( seq.cur() );

    definedFunctions.insert(func);
    return true;

badfunc:
    cout << "ERROR: Invalid function definition";
    if( !func.name.empty() ) cout << " '" << func.name << "'";
    cout << "." << endl;
    return false;
}

void interpret( token_sequence& seq ) {
    bool ok=true;
    while( ok && !seq.empty() ) {
        if( seq.cur()=="F" )
            ok = defineFunction(seq);
        else if( seq.cur()=="=" && !seq.isNext("[") )
            ok = opAssignment(seq);
        else if( seq.cur()=="then" )
            ok = opThen(seq);
        else if( seq.cur()=="else" )
            ok = opElse(seq);
        else if( seq.cur()=="?" )   // "?" is ignored since it is mostly just a placeholder
            seq.next();
        else
            ok = interpStatement(seq);
    }
}

int main (int argc, char * const argv[]) {
    initSystem();
    token_sequence seq;
    string input;

    if( argc > 1 ) {
        ifstream f( argv[1] );
        if( f.is_open() ) {
            while( !f.eof() ) {
                getline( f, input );
                token_sequence seq( getTokens(input) );;
                interpret(seq);
            }
        } else {
            cout << "could not open file '" << argv[1] << "'" << endl;
        }
    } else {
        cout << "Welcome to 3code.\n\n";
        while(1) {
            cout << "=> ";
            getline(cin, input);
            token_sequence seq( getTokens(input) );
            interpret(seq);
        }
    }

    return 0;
}
