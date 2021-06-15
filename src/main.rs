extern crate yaml_rust;
extern crate clap;

use std::fs::File;
use std::io::prelude::*;
use yaml_rust::yaml::{Hash, Yaml};
use yaml_rust::{YamlLoader, YamlEmitter};
// use serde_yaml; // 0.8.7
use clap::{Arg, App, SubCommand};
// use std::collections::HashSet;

// use git2::Repository;

fn build_cli(_config: &str, _build: &str, _args: &str) {
    let mut file_build = File::open(_build).expect("Unable to open build file.");
    let mut contents_build = String::new();
    
    file_build.read_to_string(&mut contents_build)
        .expect("Unable to read build file.");

    let docs = YamlLoader::load_from_str(&contents_build).unwrap();
    /*

    // Multi document support, doc is a yaml::Yaml
    let doc = &docs[0];

    // Debug support
    println!("{:?}", doc);

    // Index access for map & array
    assert_eq!(doc["foo"][0].as_str().unwrap(), "list1");
    assert_eq!(doc["bar"][1].as_f64().unwrap(), 2.0);

    // Chained key/array access is checked and won't panic,
    // return BadValue if they are not exist.
    assert!(doc["INVALID_KEY"][100].is_badvalue());
    */

    // Dump the YAML object
    let mut out_str = String::new();
    {
        let mut emitter = YamlEmitter::new(&mut out_str);
        emitter.dump(docs[]).unwrap(); // dump the YAML object to a String
    }
    println!("{}", out_str);
}


fn main() {
    let matches = App::new("yamake")
                          .version("0.4")
                          .author("Daniel Rollings <daniel.rollings@gmail.com>")
                          .about("Does awesome things")
                          .arg(Arg::with_name("config")
                               .short("c")
                               .long("config")
                               .value_name("FILE")
                               .help("Sets a custom config file")
                               .takes_value(true))
                          .arg(Arg::with_name("build")
                               .short("b")
                               .long("build")
                               .value_name("FILE")
                               .help("Sets a custom build file")
                               .takes_value(true))
                          .arg(Arg::with_name("INPUT")
                               .help("Specifies targets to build")
                               .required(false)
                               .multiple(true)
                               .index(1))
                          .arg(Arg::with_name("v")
                               .short("v")
                               .multiple(true)
                               .help("Sets the level of verbosity"))
                          .subcommand(SubCommand::with_name("test")
                                      .about("controls testing features")
                                      .version("0.1")
                                      .author("Daniel Rollings <daniel.rollings@gmail.com>")
                                      .arg(Arg::with_name("debug")
                                          .short("d")
                                          .help("print debug information verbosely")))
                          .get_matches();

    /*
    let mut a: HashSet<i32> = vec![1i32, 2, 3].into_iter().collect();
    let mut b: HashSet<i32> = vec![1i32, 2, 3].into_iter().collect();

    a.insert(11);
    a.insert(13);
    a.insert(17);
    
    b.insert(2);
    b.insert(6);
    // assert_eq!(b.is_subset(&a), true);
    */


    let _config = matches.value_of("config").unwrap_or("yamake_config.yaml");
    let _build = matches.value_of("build").unwrap_or("yamake.yaml");
    let _args = matches.value_of("INPUT").unwrap();
    println!("Building using {}", _build);

    /*
    // Vary the output based on how many times the user used the "verbose" flag
    // (i.e. 'myprog -v -v -v' or 'myprog -vvv' vs 'myprog -v'
    match matches.occurrences_of("v") {
        0 => println!("No verbose info"),
        1 => println!("Some verbose info"),
        2 => println!("Tons of verbose info"),
        3 | _ => println!("Don't be crazy"),
    }

    // You can handle information about subcommands by requesting their matches by name
    // (as below), requesting just the name used, or both at the same time
    if let Some(matches) = matches.subcommand_matches("test") {
        if matches.is_present("debug") {
            println!("Printing debug info...");
        } else {
            println!("Printing normally...");
        }
    }
    */

    build_cli(_config, _build, _args)

    // more program logic goes here...
}
